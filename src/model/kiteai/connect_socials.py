import random
import asyncio
import secrets
from loguru import logger
from curl_cffi.requests import AsyncSession

from src.model.kiteai.constants import KiteAIProtocol
from src.utils.decorators import retry_async


class ConnectSocials:
    def __init__(self, kiteai_instance: KiteAIProtocol):
        self.kiteai = kiteai_instance

    async def connect_socials(self):
        try:
            success = True
            logger.info(f"{self.kiteai.account_index} | Starting connect socials...")

            account_info = await self.kiteai.get_account_info()

            if account_info is None:
                raise Exception("Account info is None")

            if account_info["social_accounts"]["twitter"]["id"] == "":
                if not self.kiteai.twitter_token:
                    logger.error(
                        f"{self.kiteai.account_index} | Twitter token is None. Please add token to data/twitter_tokens.txt"
                    )
                else:
                    if not await self.connect_twitter():
                        success = False
            else:
                logger.success(
                    f"{self.kiteai.account_index} | Twitter already connected"
                )

            if account_info["social_accounts"]["discord"]["id"] == "":
                if not self.kiteai.discord_token:
                    logger.error(
                        f"{self.kiteai.account_index} | Discord token is None. Please add token to data/discord_tokens.txt"
                    )
                else:
                    if not await self.connect_discord():
                        success = False
            else:
                logger.success(
                    f"{self.kiteai.account_index} | Discord already connected"
                )

            if success:
                logger.success(
                    f"{self.kiteai.account_index} | Successfully connected socials"
                )
            else:
                logger.error(f"{self.kiteai.account_index} | Failed to connect socials")

            return success

        except Exception as e:
            random_pause = random.randint(
                self.kiteai.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.kiteai.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.kiteai.account_index} | Connect socials error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            return False

    @retry_async(default_value=False)
    async def connect_twitter(self):
        try:
            logger.info(f"{self.kiteai.account_index} | Starting connect twitter...")

            generated_csrf_token = secrets.token_hex(16)

            cookies = {"ct0": generated_csrf_token, "auth_token": self.kiteai.twitter_token}
            cookies_headers = "; ".join(f"{k}={v}" for k, v in cookies.items())

            headers = {
                "cookie": cookies_headers,
                "x-csrf-token": generated_csrf_token,
                'upgrade-insecure-requests': '1',
                "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            }

            client_id = "YW1nN2RHYmtEVV9odHNOSEZ2SEE6MTpjaQ"
            code_challenge = "challenge"
            state = "state"
            params = {
                'client_id': client_id,
                'code_challenge': code_challenge,
                'code_challenge_method': 'plain',
                'redirect_uri': 'https://testnet.gokite.ai/twitter',
                'response_type': 'code',
                'scope': 'tweet.read users.read',
                'state': state,
            }

            response = await self.kiteai.session.get('https://x.com/i/api/2/oauth2/authorize', params=params, headers=headers)

            if not response.json().get("auth_code"):
                raise Exception(f"Failed to connect twitter: no auth_code in response: {response.status_code} | {response.text}")
            
            auth_code = response.json().get("auth_code")

            data = {
                'approval': 'true',
                'code': auth_code,
            }

            response = await self.kiteai.session.post('https://x.com/i/api/2/oauth2/authorize', headers=headers, data=data)
        
            redirect_url = response.json()['redirect_uri']

            headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'referer': 'https://twitter.com/',
                'priority': 'u=0, i',
            }

            response = await self.kiteai.session.get(redirect_url, headers=headers)

            headers = {
                'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'upgrade-insecure-requests': '1',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'sec-fetch-site': 'cross-site',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-user': '?1',
                'sec-fetch-dest': 'document',
                'referer': 'https://x.com/',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'priority': 'u=0, i',
            }

            curl_session = AsyncSession(
                impersonate="chrome131",
                proxies={"http": f"http://{self.kiteai.proxy}", "https": f"http://{self.kiteai.proxy}"},
                verify=False,
            )
            
            params = {
                'state': 'state',
                'code': auth_code,
            }
            response = await curl_session.get('https://testnet.gokite.ai/twitter', params=params, headers=headers, allow_redirects=False)

            location = response.headers.get('location')
            if not location:
                raise Exception(f"Failed to connect twitter send auth_code: no location in response: {response.status_code} | {response.text}")
            
            location_token = location.split('token=')[1]

            response = await curl_session.get(location, headers=headers, allow_redirects=False)

            if response.status_code != 200:
                raise Exception(f"Failed to connect twitter send auth_code: status code is {response.status_code} | {response.text}")

            await self.kiteai.login()

            cookie = {
                'user_session_id': self.kiteai.kiteai_login_token,
            }

            headers = {
                'sec-ch-ua-platform': '"Windows"',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
                'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
                'sec-ch-ua-mobile': '?0',
                'accept': '*/*',
                'origin': 'https://testnet.gokite.ai',
                'sec-fetch-site': 'same-origin',
                'sec-fetch-mode': 'cors',
                'sec-fetch-dest': 'empty',
                'referer': f'https://testnet.gokite.ai/twitter',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'priority': 'u=1, i',
                }

            params = {
                'token': location_token,
            }

            response = await self.kiteai.session.post('https://testnet.gokite.ai/twitter', json={}, params=params, cookies=cookie, headers=headers)

            if response.json().get("data") == "ok":
                logger.success(f"{self.kiteai.account_index} | Successfully connected twitter")
                return True
            else:
                raise Exception(f"Failed to connect twitter: {response.status_code} | {response.text}")

        except Exception as e:
            if "Could not authenticate you" in str(e):
                logger.error(f"{self.kiteai.account_index} | Twitter token is invalid")
                return False
            
            random_pause = random.randint(
                self.kiteai.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.kiteai.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.kiteai.account_index} | Connect twitter error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=False)
    async def connect_discord(self):
        try:
            logger.info(f"{self.kiteai.account_index} | Starting connect discord...")

            headers = {
                "Referer": "https://testnet.gokite.ai/",
                "Upgrade-Insecure-Requests": "1",
            }

            response = await self.kiteai.session.get(
                "https://discord.com/oauth2/authorize?response_type=code&client_id=1355842034900013246&redirect_uri=https%3A%2F%2Ftestnet.gokite.aik%2Fdiscord&scope=identify",
                headers=headers,
            )

            headers = {
                'authorization': self.kiteai.discord_token,
                'referer': 'https://discord.com/oauth2/authorize?response_type=code&client_id=1355842034900013246&redirect_uri=https%3A%2F%2Ftestnet.gokite.ai%2Fdiscord&scope=identify',
                'x-debug-options': 'bugReporterEnabled',
                'x-discord-locale': 'en-US',
              } 

            params = {
                'client_id': '1355842034900013246',
                'response_type': 'code',
                'redirect_uri': 'https://testnet.gokite.ai/discord',
                'scope': 'identify',
                'integration_type': '0',
            }

            response = await self.kiteai.session.get('https://discord.com/api/v9/oauth2/authorize', params=params, headers=headers)
                        
            headers = {
                'authorization': self.kiteai.discord_token,
                'content-type': 'application/json',
                'origin': 'https://discord.com',
                'referer': 'https://discord.com/oauth2/authorize?response_type=code&client_id=1355842034900013246&redirect_uri=https%3A%2F%2Ftestnet.gokite.ai%2Fdiscord&scope=identify',
                'x-debug-options': 'bugReporterEnabled',
                'x-discord-locale': 'en-US',
                }

            params = {
                'client_id': '1355842034900013246',
                'response_type': 'code',
                'redirect_uri': 'https://testnet.gokite.ai/discord',
                'scope': 'identify',
            }

            json_data = {
                'permissions': '0',
                'authorize': True,
                'integration_type': 0,
                'location_context': {
                    'guild_id': '10000',
                    'channel_id': '10000',
                    'channel_type': 10000,
                },
                'dm_settings': {
                    'allow_mobile_push': False,
                },
            }

            response = await self.kiteai.session.post(
                'https://discord.com/api/v9/oauth2/authorize',
                params=params,
                headers=headers,
                json=json_data,
            )

            if not response.json()['location']:
                raise Exception("Failed to connect discord: no location in response")
            
            headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'referer': 'https://discord.com/',
                'upgrade-insecure-requests': '1',
                }

            
            code = response.json()['location'].split('code=')[1].split('&')[0]

            response = await self.kiteai.session.get(response.json()['location'], headers=headers)

            if response.status_code != 200:
                raise Exception(f"Failed to connect discord: status code is {response.status_code} | {response.text}")


            headers = {
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'upgrade-insecure-requests': '1',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'sec-fetch-site': 'cross-site',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-user': '?1',
                'sec-fetch-dest': 'document',
                'referer': 'https://discord.com/',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'priority': 'u=0, i',
            }


            curl_session = AsyncSession(
                impersonate="chrome131",
                proxies={"http": f"http://{self.kiteai.proxy}", "https": f"http://{self.kiteai.proxy}"},
                verify=False,
            )
            
            params = {
                'code': code,
            }
            response = await curl_session.get('https://testnet.gokite.ai/discord', params=params, headers=headers, allow_redirects=False)

            location = response.headers.get('location')
            location_token = location.split('token=')[1]
            if not location:
                raise Exception(f"Failed to connect discord send auth_code: no location in response: {response.status_code} | {response.text}")
            
            response = await curl_session.get(location, headers=headers, allow_redirects=False)
            

            cookies = {
                'user_session_id': self.kiteai.kiteai_login_token,
            }

            headers = {
                'sec-ch-ua-platform': '"Windows"',
                'sec-ch-ua-mobile': '?0',
                'accept': '*/*',
                'sec-gpc': '1',
                'accept-language': 'en-US,en;q=0.5',
                'origin': 'https://testnet.gokite.ai',
                'sec-fetch-site': 'same-origin',
                'sec-fetch-mode': 'cors',
                'sec-fetch-dest': 'empty',
                'referer': 'https://testnet.gokite.ai/discord',
                'priority': 'u=1, i',
                }

            params = {
                'token': location_token,
            }

            response = await self.kiteai.session.post('https://testnet.gokite.ai/discord', params=params, cookies=cookies, headers=headers)
            if response.json().get("data") == "ok":
                logger.success(f"{self.kiteai.account_index} | Successfully connected discord")
                return True
            else:
                raise Exception(f"Failed to connect discord: {response.status_code} | {response.text}")
            
        except Exception as e:
            random_pause = random.randint(
                self.kiteai.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.kiteai.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.kiteai.account_index} | Connect discord error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise