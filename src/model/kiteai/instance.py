import asyncio
from typing import List
from datetime import datetime
import random
import os
import binascii
from eth_account import Account, account
from loguru import logger
import primp
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from src.model.kiteai.connect_socials import ConnectSocials
from src.model.kiteai.ozone_ai_chat import OzoneAIChat
from src.model.kiteai.swaps import KiteSwaps
from src.model.help.captcha import Capsolver, Solvium
from src.model.onchain.web3_custom import Web3Custom
from src.model.kiteai.constants import ACCOUNT_FACTORY_ABI, ACCOUNT_FACTORY_ADDRESS, SALT, STAKE_CONTRACT_ADDRESSES
from src.utils.config import Config
from src.utils.decorators import retry_async
from src.utils.constants import EXPLORER_URL_KITEAI


class KiteAI:
    def __init__(
        self,
        account_index: int,
        session: primp.AsyncClient,
        web3: Web3Custom,
        config: Config,
        wallet: Account,
        proxy: str,
        discord_token: str,
        twitter_token: str,
    ):
        self.account_index = account_index
        self.session = session
        self.web3 = web3
        self.config = config
        self.wallet = wallet
        self.proxy = proxy
        self.discord_token = discord_token
        self.twitter_token = twitter_token

        # Инициализируем сервисы
        self.kiteai_login_token: str = ""
        self.kiteai_signin_token: str = ""
        self.eoa_address: str = ""

    @retry_async(default_value=None)
    async def request_eoa_address(self) -> str:
        try:
            # Convert salt from hex string to integer
            salt_int = int(SALT, 16)
            
            # Create contract instance
            contract = self.web3.web3.eth.contract(
                address=ACCOUNT_FACTORY_ADDRESS,
                abi=ACCOUNT_FACTORY_ABI
            )
            
            # Get EOA address using the factory contract
            eoa_address = await contract.functions.getAddress(
                self.wallet.address,
                salt_int
            ).call()
            
            logger.success(f"{self.account_index} | EOA address retrieved: {eoa_address}")
            return eoa_address
            
        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Request EOA address error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=False)
    async def login(self) -> bool:
        try:
            self.kiteai_signin_token = await self.__create_auth_token(self.wallet.address)
            headers = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'authorization': self.kiteai_signin_token,
                'content-type': 'application/json',
                'origin': 'https://testnet.gokite.ai',
                'priority': 'u=1, i',
                'referer': 'https://testnet.gokite.ai/landing',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
            }

            json_data = {
                'eoa': self.wallet.address,
            }

            response = await self.session.post('https://testnet.gokite.ai/api/signin', headers=headers, json=json_data)

            if "aa address is not found" in response.text:
                self.eoa_address = await self.request_eoa_address()
                if not self.eoa_address:
                    raise Exception("Failed to get EOA address")
                
                json_data = {
                    'eoa': self.wallet.address,
                    'aa_address': self.eoa_address,
                }

                response = await self.session.post('https://testnet.gokite.ai/api/signin', headers=headers, json=json_data)

            if not response.json().get("data", {}).get("access_token", None):
                if response.json().get("error", None):
                    raise Exception(response.json()["error"])
                else:
                    raise Exception(f"Failed to get login token: {response.json()}")
            
            self.kiteai_login_token = response.json().get("data", {}).get("access_token", None)
            self.eoa_address = response.json().get("data", {}).get("aa_address", None)

            logger.success(f"{self.account_index} | Successfully logged in KiteAI Ozone")

            await self.get_account_info()

            return True

        except Exception as e:
            import traceback
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Login error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=False)
    async def faucet(self) -> bool:
        try:

            if self.config.FAUCET.USE_CAPSOLVER:
                logger.info(
                    f"[{self.account_index}] | Solving Recaptcha challenge with Capsolver..."
                )
                capsolver = Capsolver(
                    api_key=self.config.FAUCET.CAPSOLVER_API_KEY,
                    proxy=self.proxy,
                    session=self.session,
                )
                captcha_result = await capsolver.solve_recaptcha(
                    "6Lc_VwgrAAAAALtx_UtYQnW-cFg8EPDgJ8QVqkaz",
                    "https://testnet.gokite.ai/",
                )
            else:
                logger.info(
                    f"[{self.account_index}] | Solving Recaptcha challenge with Solvium..."
                )
                solvium = Solvium(
                    api_key=self.config.FAUCET.SOLVIUM_API_KEY,
                    session=self.session,
                    proxy=self.proxy,
                )

                result = await solvium.solve_recaptcha(
                    sitekey="6Lc_VwgrAAAAALtx_UtYQnW-cFg8EPDgJ8QVqkaz",
                    pageurl="https://testnet.gokite.ai/",
                    version="v2",
                )
                captcha_result = result

            if not captcha_result:
                raise Exception("Failed to solve Recaptcha challenge")

            logger.success(f"[{self.account_index}] | Recaptcha challenge solved")

            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'authorization': f'Bearer {self.kiteai_login_token}',
                'content-type': 'application/json',
                'origin': 'https://testnet.gokite.ai',
                'priority': 'u=1, i',
                'referer': 'https://testnet.gokite.ai/',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'x-recaptcha-token': captcha_result,
            }

            json_data = {}

            response = await self.session.post('https://ozone-point-system.prod.gokite.ai/blockchain/faucet-transfer', headers=headers, json=json_data)

            status_code = response.status_code

            if "Already claimed today" in response.text:
                logger.success(f"[{self.account_index}] | Already claimed today")
                return True

            if status_code <200 or status_code >=300:
                raise Exception(f"Failed to send claim request: {response.text}")

            try:
                response_json = response.json()
            except Exception:
                raise Exception(f"Invalid JSON response: {response.text}")

            if not isinstance(response_json, dict):
                raise Exception(f"Response is not JSON object: {response.text}")

            if "data" not in response_json:
                raise Exception(f"Missing 'data' field in response: {response.text}")

            data = response_json.get("data")
            
            # Handle both cases: data as string "ok" or as object with "ok" field
            if isinstance(data, str) and data == "ok":
                logger.success(f"[{self.account_index}] | Successfully got tokens from faucet")
                return True
            elif isinstance(data, dict):
                if "ok" not in data:
                    raise Exception(f"Missing 'ok' field in data: {response.text}")
                
                if data.get("ok"):
                    logger.success(f"[{self.account_index}] | Successfully got tokens from faucet")
                    return True
                else:
                    raise Exception(f"Faucet request failed: {response.text}")
            else:
                raise Exception(f"Unexpected data format: {response.text}")
            
        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Faucet error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise
    
    @retry_async(default_value=False)
    async def faucet_onchain(self) -> bool:
        try:

            if self.config.FAUCET.USE_CAPSOLVER:
                logger.info(
                    f"[{self.account_index}] | Solving Recaptcha challenge with Capsolver..."
                )
                capsolver = Capsolver(
                    api_key=self.config.FAUCET.CAPSOLVER_API_KEY,
                    proxy=self.proxy,
                    session=self.session,
                )
                captcha_result = await capsolver.solve_recaptcha(
                    "6LeNaK8qAAAAAHLuyTlCrZD_U1UoFLcCTLoa_69T",
                    "https://faucet.gokite.ai/",
                )
            else:
                logger.info(
                    f"[{self.account_index}] | Solving Recaptcha challenge with Solvium..."
                )
                solvium = Solvium(
                    api_key=self.config.FAUCET.SOLVIUM_API_KEY,
                    session=self.session,
                    proxy=self.proxy,
                )

                result = await solvium.solve_recaptcha(
                    sitekey="6LeNaK8qAAAAAHLuyTlCrZD_U1UoFLcCTLoa_69T",
                    pageurl="https://faucet.gokite.ai/",
                    version="v2",
                )
                captcha_result = result

            if not captcha_result:
                raise Exception("Failed to solve Recaptcha challenge")

            logger.success(f"[{self.account_index}] | Recaptcha challenge solved")

            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'authorization': f'Bearer {self.kiteai_login_token}',
                'content-type': 'application/json',
                'origin': 'https://faucet.gokite.ai',
                'priority': 'u=1, i',
                'referer': 'https://faucet.gokite.ai/',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'x-recaptcha-token': captcha_result,
            }

            json_data = {
                'address': self.wallet.address,
                'token': '',
                'v2Token': captcha_result,
                'chain': 'KITE',
                'couponId': '',
            }

            response = await self.session.post('https://faucet.gokite.ai/api/SendToken', headers=headers, json=json_data)

            response_json = response.json()
            status_code = response.status_code

            if "Too many requests" in response.text or status_code == 429:
                logger.warning(f"[{self.account_index}] | Faucet already claimed today, wait...")
                return True

            if status_code <200 or status_code >=300:
                raise Exception(f"Failed to send claim request: {response.text}")

            tx_hash = response_json.get("txHash", "")
            if tx_hash:
                logger.success(f"[{self.account_index}] | Transaction sent: {EXPLORER_URL_KITEAI}{tx_hash}")
                return True
            else:
                raise Exception(f"Failed to send claim request: {response.text}")
            
        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Faucet error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=False)
    async def get_account_info(self, log: bool = False) -> dict:
        '''
        Response like this:
        {
            "data": {
                "badges": [],
                "daily_quiz_completed": bool,
                "faucet_claimable": bool,
                "onboarding_quiz_completed": bool,
                "profile": {
                    "badges_minted": None,
                    "displayed_name": str,
                    "eoa_address": str,
                    "percentile": int,
                    "picture_url": str,
                    "rank": int,
                    "referral_code": str,
                    "referrals_count": int,
                    "smart_account_address": str,
                    "total_v1_xp_points": int,
                    "total_xp_points": int,
                    "user_id": int,
                    "username": str
                },
                "social_accounts": {
                    "discord": {
                        "action_types": [
                            {
                                "action_type_name": str,
                                "id": int,
                                "is_completed": bool,
                                "xp_point": int
                            }
                        ],
                        "id": str,
                        "username": str
                    },
                    "telegram": {
                        "action_types": [],
                        "id": str,
                        "username": str
                    },
                    "twitter": {
                        "action_types": [
                            {
                                "action_type_name": str,
                                "id": int,
                                "is_completed": bool,
                                "xp_point": int
                            }
                        ],
                        "id": str,
                        "username": str
                    }
                }
            },
            "error": str
        }
        '''
        try:
            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'authorization': f'Bearer {self.kiteai_login_token}',
                'origin': 'https://testnet.gokite.ai',
                'priority': 'u=1, i',
                'referer': 'https://testnet.gokite.ai/',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            }

            response = await self.session.get('https://ozone-point-system.prod.gokite.ai/me', headers=headers)
            response_json = response.json()
            status_code = response.status_code

            if "User does not exist" in response.text:
                headers = {
                    'accept': 'application/json, text/plain, */*',
                    'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                    'authorization': f'Bearer {self.kiteai_login_token}',
                    'content-type': 'application/json',
                    'origin': 'https://testnet.gokite.ai',
                    'priority': 'u=1, i',
                    'referer': 'https://testnet.gokite.ai/',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
                    'sec-fetch-dest': 'empty',
                    'sec-fetch-mode': 'cors',
                    'sec-fetch-site': 'same-site',
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                }

                json_data = {
                    'registration_type_id': 1,
                    'user_account_id': '',
                    'user_account_name': '',
                    'eoa_address': self.wallet.address,
                    'smart_account_address': self.eoa_address,
                    'referral_code': None, # TODO: add referral code
                }

                response = await self.session.post('https://ozone-point-system.prod.gokite.ai/auth', headers=headers, json=json_data)

                response_json = response.json()
                status_code = response.status_code

                if status_code <200 or status_code >=300:
                    raise Exception(f"Failed to auth user: {response.text}")

            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'authorization': f'Bearer {self.kiteai_login_token}',
                'origin': 'https://testnet.gokite.ai',
                'priority': 'u=1, i',
                'referer': 'https://testnet.gokite.ai/',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            }

            response = await self.session.get('https://ozone-point-system.prod.gokite.ai/me', headers=headers)
            response_json = response.json()
            status_code = response.status_code

            if status_code <200 or status_code >299:
                raise Exception(f"Failed to get user info: {response.text}")

            if response_json["error"] == "":
                if log:
                    logger.success(f"[{self.account_index}] | Successfully got user info")
                    self._display_account_info(response_json["data"])
                return response_json["data"]
            else:
                raise Exception(f"Failed to get user info: {response.text}")
            
        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Get account info error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise
    
    @retry_async(default_value=False)
    async def _sumbit_quiz(self, question_id: int, answer: str, finish: bool, quiz_id: int = None) -> bool:
        try:
            if quiz_id:
                URL_QUIZ_SUBMIT = "https://neo.prod.gokite.ai/v2/quiz/submit"
            else:
                URL_QUIZ_SUBMIT = "https://neo.prod.gokite.ai/v2/quiz/onboard/submit"

            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'authorization': f'Bearer {self.kiteai_login_token}',
                'content-type': 'application/json',
                'origin': 'https://testnet.gokite.ai',
                'priority': 'u=1, i',
                'referer': 'https://testnet.gokite.ai/',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            }

            json_data = {
                'question_id': question_id,
                'answer': answer,
                'finish': finish,
                'eoa': self.wallet.address.lower(),
            }

            if quiz_id:
                json_data['quiz_id'] = quiz_id
                json_data['eoa'] = self.wallet.address

            response = await self.session.post(URL_QUIZ_SUBMIT, headers=headers, json=json_data)

            if response.json().get('data').get('result')  == 'RIGHT':
                logger.success(f"[{self.account_index}] | Successfully submitted quiz")
                return True
            else:
                raise Exception(f"Failed to submit quiz: {response.text}")
            
        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Submit quiz error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=False)
    async def complete_quiz(self) -> bool:
        try:
            account_info = await self.get_account_info()
            if not account_info.get("data", {}).get("onboarding_quiz_completed", None):
                quiz_data = await self._start_quiz()
                if quiz_data.get("quiz", None).get("user_id", None) == "ONBOARD":
                    questions = quiz_data.get("question", [])
                    for question in questions:
                        end = False
                        if 'Which subnet type in Kite AI provides' in question['content']:
                            end = True

                        await self._sumbit_quiz(question_id=question['question_id'], answer=question['answer'], finish=end)
                        await asyncio.sleep(random.randint(3, 10))

                else:
                    logger.error(f"[{self.account_index}] | Failed to start onboarding quiz")

            if not account_info.get("data", {}).get("daily_quiz_completed", None):
                quiz_data = await self._daily_quiz()
                quiz_id = quiz_data.get("quiz", None).get("quiz_id", None)
                questions = quiz_data.get("question", [])

                if len(questions) > 0:
                    for question in questions:
                        await self._sumbit_quiz(question_id=question['question_id'], answer=question['answer'], finish=True, quiz_id=quiz_id)
                        await asyncio.sleep(random.randint(3, 10))

            # if account_info.get("data", {}).get("faucet_claimable", None):
            #     await self.faucet()
            #     await self.faucet_onchain()
            return True

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Onboard quiz error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise
    
    @retry_async(default_value=None)
    async def _start_quiz(self) -> dict:
        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
            'authorization': f'Bearer {self.kiteai_login_token}',
            'content-type': 'application/json',
            'priority': 'u=1, i',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        }

        data = {
            'eoa': self.wallet.address.lower()
        }
        response = await self.session.get("https://neo.prod.gokite.ai/v2/quiz/onboard/get", headers=headers, params=data)

        data = response.json().get('data', None)

        return data

    @retry_async(default_value=None)
    async def _daily_quiz(self) -> dict:
        try:
            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'authorization': f'Bearer {self.kiteai_login_token}',
                'content-type': 'application/json',
                'origin': 'https://testnet.gokite.ai',
                'priority': 'u=1, i',
                'referer': 'https://testnet.gokite.ai/',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                }
            now = datetime.utcnow()
            date = now.strftime("%Y-%m-%d")

            json_data = {
                'title': f'daily_quiz_{date}',
                'num': 1,
                'eoa': self.wallet.address,
            }

            response = await self.session.post("https://neo.prod.gokite.ai/v2/quiz/create", headers=headers, json=json_data)
            
            if response.json().get('data').get('status') == 0:
                params = {
                    "id": str(response.json().get('data').get('quiz_id')),
                    "eoa": self.wallet.address,
                }
                resp = await self.session.get("https://neo.prod.gokite.ai/v2/quiz/get", headers=headers, params=params)
                if resp.status_code <200 or resp.status_code >299:
                    pass
                else:
                    return resp.json().get('data')

            return response.json().get('data')

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Daily quiz error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise
    
    @retry_async(default_value=None)
    async def get_balance(self) -> dict:
        '''
        {
            "data": {
                "balances": {
                    "kite": float,
                    "usdt": float
                }
            },
            "error": str
        }
        '''
        try:
            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'authorization': f'Bearer {self.kiteai_login_token}',
                'origin': 'https://testnet.gokite.ai',
                'priority': 'u=1, i',
                'referer': 'https://testnet.gokite.ai/',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
            }

            response = await self.session.get('https://ozone-point-system.prod.gokite.ai/me/balance', headers=headers)
            error = response.json().get("error")
            if response.status_code <200 or response.status_code >299 or error:
                raise Exception(f"Failed to get balance: {response.text}")
            else:
                kiteai_balance = response.json().get('data').get('balances').get('kite')
                usdt_balance = response.json().get('data').get('balances').get('usdt')
                logger.success(f"[{self.account_index}] | KiteAI balance: {kiteai_balance}, USDT balance: {usdt_balance}")

                return response.json().get('data')

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Get balance error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=None)
    async def _get_badges(self) -> List[dict]:
        try:
            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'authorization': f'Bearer {self.kiteai_login_token}',
                'origin': 'https://testnet.gokite.ai',
                'priority': 'u=1, i',
                'referer': 'https://testnet.gokite.ai/',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
            }

            response = await self.session.get('https://ozone-point-system.prod.gokite.ai/badges', headers=headers)
            error = response.json().get("error")
            if response.status_code <200 or response.status_code >299 or error:
                raise Exception(f"Failed to get badges: {response.text}")
            else:
                return response.json().get('data')

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Get badges error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise
    
    @retry_async(default_value=None)
    async def mint_badges(self) -> dict:
        try:
            badges = await self._get_badges()
            account_info = await self.get_account_info()

            if not badges or not account_info:
                raise Exception(f"[{self.account_index}] | Failed to get badges or account info")

            available_badges = [available_badge for available_badge in badges if available_badge["isEligible"]]
            if not available_badges:
                logger.warning(f"[{self.account_index}] | No eligible badges found.")
                return True

            user_badges = account_info["profile"]["badges_minted"]
            
            if not user_badges:
                badges_to_mint = available_badges
            else:
                badges_to_mint = [badge for badge in available_badges if badge["collectionId"] not in user_badges]
            
            if not badges_to_mint:
                logger.warning(f"[{self.account_index}] | All eligible badges already minted.")
                return True
            
            for badge in badges_to_mint:
                await self._claim_badge(badge["collectionId"])
                await asyncio.sleep(random.randint(3, 10))

            return True

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Mint badges error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise


    @retry_async(default_value=None)
    async def _claim_badge(self, badge_id) -> dict:
        try:
            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'authorization': f'Bearer {self.kiteai_login_token}',
                'origin': 'https://testnet.gokite.ai',
                'priority': 'u=1, i',
                'referer': 'https://testnet.gokite.ai/',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
            }

            data = {
                "badge_id": int(badge_id),
            }
            response = await self.session.post('https://ozone-point-system.prod.gokite.ai/badges/mint', headers=headers, json=data)

            error = response.json().get("error")
            if "You have minted the badge" in response.text:
                logger.success(f"[{self.account_index}] | Already claimed badge {badge_id}")
                return True
            
            if response.status_code <200 or response.status_code >299 or error:
                raise Exception(f"Failed to claim badge: {response.text}")
            else:
                logger.success(f"[{self.account_index}] | Successfully claimed badge {badge_id}")
                return response.json().get('data')

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Claim badge error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise
    
    @retry_async(default_value=None)
    async def stake(self) -> bool:
        try:
            if self.config.STAKINGS.GOKITE.UNSTAKE:
                logger.warning(f"[{self.account_index}] | Unstaking is not implemented yet")
                return True
                # staked_balance = await self._get_stake_info()

                # if staked_balance > 0:
                #     return await self._unstake(staked_balance)

            balance = await self.get_balance()
            kite_balance = balance["balances"]["kite"]
            
            if kite_balance < 1:
                raise Exception(f"[{self.account_index}] | Not enough balance to stake: {kite_balance} Kite")
            
            # Get random amount from config range (can be float)
            min_amount = self.config.STAKINGS.GOKITE.KITE_AMOUNT_TO_STAKE[0]
            max_amount = self.config.STAKINGS.GOKITE.KITE_AMOUNT_TO_STAKE[1]
            desired_amount = random.uniform(min_amount, max_amount)
            
            # If balance is less than desired amount, use percentage of balance
            if kite_balance < desired_amount:
                # Use 80-90% of balance but ensure minimum 1 token
                percentage = random.uniform(0.8, 0.9)
                amount = max(1.0, kite_balance * percentage)
            else:
                amount = desired_amount
            
            # Ensure we don't stake more than available balance
            amount = min(amount, kite_balance)
            
            logger.info(f"[{self.account_index}] | Staking {amount:.6f} KITE (balance: {kite_balance:.6f})")
            await self._stake(amount=amount)
            return True
        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Stake error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=None)
    async def _stake(self, amount: float) -> bool:
        try:
            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'authorization': f'Bearer {self.kiteai_login_token}',
                'origin': 'https://testnet.gokite.ai',
                'priority': 'u=1, i',
                'referer': 'https://testnet.gokite.ai/',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
            }

            sub = random.choice(list(STAKE_CONTRACT_ADDRESSES.keys()))
            balance_data = await self.get_balance()
            kite_balance = balance_data["balances"]["kite"]
            if kite_balance < amount:
                raise Exception(f"[{self.account_index}] | Not enough balance to stake")

            data = {
                "amount": amount,
                "subnet_address": STAKE_CONTRACT_ADDRESSES[sub],
            }

            response = await self.session.post('https://ozone-point-system.prod.gokite.ai/subnet/delegate', headers=headers, json=data)
            
            if response.status_code != 200:
                raise Exception(f"Failed to stake: {response.text}")
            else:
                tx_hash = response.json().get('data').get('tx_hash')
                logger.success(f"[{self.account_index}] | Successfully staked {amount:.6f} KITE to {sub} TX: {EXPLORER_URL_KITEAI}{tx_hash}")
                return True

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Stake error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=None)
    async def _get_stake_info(self) -> dict:
        try:
            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'authorization': f'Bearer {self.kiteai_login_token}',
                'origin': 'https://testnet.gokite.ai',
                'priority': 'u=1, i',
                'referer': 'https://testnet.gokite.ai/',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
            }

            response = await self.session.get('https://ozone-point-system.prod.gokite.ai/me/staked', headers=headers)

            error = response.json().get("error")
            if response.status_code <200 or response.status_code >299 or error:
                raise Exception(f"Failed to get badges: {response.text}")
            else:
                return response.json().get('data').get('total_staked_amount')

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Get stake info error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    async def __create_auth_token(self, wallet_address: str) -> str:
        """Generate encrypted authentication token from wallet address"""
        # Validate wallet address format
        if not wallet_address or not wallet_address.startswith("0x") or len(wallet_address) != 42:
            raise ValueError("Wallet address must be valid 0x-prefixed format")

        # Generate encryption key from predefined hex string
        encryption_key = self._extract_key_material("6a1c35292b7c5b769ff47d89a17e7bc4f0adfe1b462981d28e0e9f7ff20b8f8a")
        
        # Create random initialization vector
        random_iv = os.urandom(12)
        
        # Initialize AES-GCM cipher for encryption
        cipher_instance = Cipher(
            algorithms.AES(encryption_key),
            modes.GCM(random_iv),
            backend=default_backend()
        ).encryptor()
        
        # Encrypt the wallet address
        encrypted_data = cipher_instance.update(wallet_address.encode("utf-8")) + cipher_instance.finalize()
        
        # Combine IV, encrypted data, and authentication tag
        final_token = random_iv + encrypted_data + cipher_instance.tag
        
        # Convert to hexadecimal string
        return binascii.hexlify(final_token).decode("ascii")
    
    def _extract_key_material(self, hex_string: str) -> bytes:
        """Extract 32-byte key from hex string for AES-256"""
        key_bytes = bytes.fromhex(hex_string)
        return key_bytes[:32]  # Use first 32 bytes for AES-256

    async def connect_socials(self) -> bool:
        try:
            connect_socials_service = ConnectSocials(self)
            return await connect_socials_service.connect_socials()

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Connect socials error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            return False

    async def ozone_ai_chat(self) -> bool:
        try:
            ozone_ai_chat_service = OzoneAIChat(self)
            return await ozone_ai_chat_service.ozone_ai_chat()

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Ozone AI chat error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    async def perform_swap(self, token_in: str = None, token_out: str = None, amount: float = None, slippage: float = 3.0) -> bool:
        """Perform a token swap"""
        try:
            swaps_service = KiteSwaps(self)
            
            if token_in and token_out and amount:
                # Manual swap with specified parameters
                return await swaps_service.perform_swap(token_in, token_out, amount, slippage)
            else:
                # Auto swap with random selection
                return await swaps_service.auto_swap()

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Swap error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            return False

    async def perform_bridge(self, token_address: str = None, dest_chain_id: int = None, amount: float = None) -> bool:
        """Bridge tokens to another chain"""
        try:
            swaps_service = KiteSwaps(self)
            
            if token_address and dest_chain_id and amount:
                # Manual bridge with specified parameters
                return await swaps_service.bridge_tokens(token_address, dest_chain_id, amount)
            else:
                # Auto bridge with random selection
                return await swaps_service.auto_bridge()

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Bridge error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            return False

    async def check_bridge_status(self) -> bool:
        """Check if wallet has interacted with bridge before"""
        try:
            swaps_service = KiteSwaps(self)
            result = await swaps_service.check_bridge_interaction()
            return result if result is not None else False

        except Exception as e:
            logger.error(f"[{self.account_index}] | Error checking bridge status: {e}")
            return False

    async def get_swap_balances(self) -> dict:
        """Get current balances for swap-supported tokens"""
        try:
            swaps_service = KiteSwaps(self)
            return await swaps_service.get_current_balances()

        except Exception as e:
            logger.error(f"[{self.account_index}] | Error getting swap balances: {e}")
            return {}

    def _display_account_info(self, data: dict) -> None:
        """Display account info in a nice table format"""
        try:
            profile = data.get("profile", {})
            if not profile:
                return
                
            logger.info(f"[{self.account_index}] | Account Information:")
            logger.info(f"[{self.account_index}] | ┌─────────────────────────────────────┐")
            
            # Display badges_minted
            badges_minted = profile.get("badges_minted")
            if badges_minted is not None:
                if isinstance(badges_minted, list) and badges_minted:
                    badges_str = ", ".join(str(badge) for badge in badges_minted)
                    logger.info(f"[{self.account_index}] | │ Badges Minted: {badges_str:<16}     │")
                elif isinstance(badges_minted, int):
                    logger.info(f"[{self.account_index}] | │ Badges Minted: {badges_minted:<16}    │")
            
            # Display rank
            rank = profile.get("rank")
            if rank is not None:
                logger.info(f"[{self.account_index}] | │ Rank:          {rank:<16}     │")
            
            # Display total_v1_xp_points
            total_v1_xp = profile.get("total_v1_xp_points")
            if total_v1_xp is not None:
                logger.info(f"[{self.account_index}] | │ V1 XP Points:  {total_v1_xp:<16}     │")
            
            # Display total_xp_points
            total_xp = profile.get("total_xp_points")
            if total_xp is not None:
                logger.info(f"[{self.account_index}] | │ Total XP:      {total_xp:<16}     │")
            
            # Display user_id
            user_id = profile.get("user_id")
            if user_id is not None:
                logger.info(f"[{self.account_index}] | │ User ID:       {user_id:<16}     │")
            
            # Display referral_code
            referral_code = profile.get("referral_code")
            if referral_code and referral_code.strip():
                logger.info(f"[{self.account_index}] | │ Referral Code: {referral_code:<16}     │")
            
            # Display referrals_count
            referrals_count = profile.get("referrals_count")
            if referrals_count is not None:
                logger.info(f"[{self.account_index}] | │ Referrals:     {referrals_count:<16}     │")
            
            logger.info(f"[{self.account_index}] | └─────────────────────────────────────┘")
            
        except Exception as e:
            logger.error(f"[{self.account_index}] | Error displaying account info: {e}")