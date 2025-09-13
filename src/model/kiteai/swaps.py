import asyncio
import random
from decimal import Decimal
from typing import Optional
from loguru import logger
from eth_abi.abi import encode as abi_encode
from src.model.onchain.web3_custom import Web3Custom
from src.model.kiteai.constants import (
    KITE_BRIDGE_ROUTER_ADDRESS,
    KITE_SWAP_ROUTER_ADDRESS,
    KITE_SWAP_FACTORY_ADDRESS,
    BRIDGE_ROUTER_ADDRESS,
    USDT_TOKEN_ADDRESS,
    WKITE_TOKEN_ADDRESS,
    DESTINATION_BLOCKCHAIN_ID,
    BASE_SEPOLIA_CHAIN_ID,
    SWAP_BRIDGE_ABI,
    KiteAIProtocol
)
from src.utils.decorators import retry_async
from src.utils.constants import EXPLORER_URL_KITEAI
from src.model.onchain.constants import Balance


class KiteSwaps:
    def __init__(self, kiteai: KiteAIProtocol):
        self.kiteai = kiteai
        self.account_index = kiteai.account_index
        self.web3 = kiteai.web3
        self.wallet = kiteai.wallet
        self.config = kiteai.config
        self.session = kiteai.session

    @retry_async(default_value=None)
    async def get_token_balance(self, token_address: str) -> Optional[Balance]:
        """Get balance of a specific token"""
        try:
            if token_address.lower() == "0x0000000000000000000000000000000000000000":
                # Native token balance
                return await self.web3.get_balance(self.wallet.address)
            else:
                # ERC20 token balance
                return await self.web3.get_token_balance(
                    wallet_address=self.wallet.address,
                    token_address=token_address,
                    token_abi=SWAP_BRIDGE_ABI
                )
        except Exception as e:
            logger.error(f"{self.account_index} | Error getting token balance: {e}")
            return None

    @retry_async(default_value=None)
    async def get_pool_address(self, token_a: str, token_b: str) -> Optional[str]:
        """Get the pool address for a token pair"""
        try:
            factory_contract = self.web3.web3.eth.contract(
                address=KITE_SWAP_FACTORY_ADDRESS,
                abi=SWAP_BRIDGE_ABI
            )
            
            pool_address = await factory_contract.functions.getPair(token_a, token_b).call()
            
            if pool_address == "0x0000000000000000000000000000000000000000":
                return None
            
            return pool_address
        except Exception as e:
            logger.error(f"{self.account_index} | Error getting pool address: {e}")
            return None

    @retry_async(default_value=None)
    async def get_pool_reserves(self, pool_address: str) -> Optional[tuple]:
        """Get reserves from a liquidity pool"""
        try:
            pool_contract = self.web3.web3.eth.contract(
                address=pool_address,
                abi=SWAP_BRIDGE_ABI
            )
            
            token0 = await pool_contract.functions.token0().call()
            token1 = await pool_contract.functions.token1().call()
            reserves = await pool_contract.functions.getReserves().call()
            
            return token0.lower(), token1.lower(), reserves[0], reserves[1]
        except Exception as e:
            logger.error(f"{self.account_index} | Error getting pool reserves: {e}")
            return None

    async def calculate_price(self, token_in: str, token_out: str, amount_in: float) -> Optional[tuple]:
        """Calculate swap price and output amount"""
        try:
            # Handle native token conversion
            if token_in.lower() == "0x0000000000000000000000000000000000000000":
                token_in = WKITE_TOKEN_ADDRESS
            if token_out.lower() == "0x0000000000000000000000000000000000000000":
                token_out = WKITE_TOKEN_ADDRESS
            
            pool_address = await self.get_pool_address(token_in, token_out)
            if not pool_address:
                logger.error(f"{self.account_index} | No pool found for pair {token_in}/{token_out}")
                return None
            
            pool_data = await self.get_pool_reserves(pool_address)
            if not pool_data:
                return None
            
            token0, token1, reserve0, reserve1 = pool_data
            
            # Determine token order and calculate price
            if token_in.lower() == token0:
                price = (Decimal(reserve1) / Decimal(10 ** 18)) / (Decimal(reserve0) / Decimal(10 ** 18))
                amount_out = float(amount_in) * float(price)
            elif token_in.lower() == token1:
                price = (Decimal(reserve0) / Decimal(10 ** 18)) / (Decimal(reserve1) / Decimal(10 ** 18))
                amount_out = float(amount_in) * float(price)
            else:
                logger.error(f"{self.account_index} | Token not found in pool")
                return None
            
            return float(price), amount_out, token0, token1
        except Exception as e:
            logger.error(f"{self.account_index} | Error calculating price: {e}")
            return None

    async def encode_trade_bytes(self, token_in: str, token_out: str, amount_out_wei: int, amount_out_min_wei: int) -> bytes:
        """Encode trade data for swap transaction"""
        try:
            # Handle native token conversion for encoding
            if token_in.lower() == "0x0000000000000000000000000000000000000000":
                token_in = WKITE_TOKEN_ADDRESS
            if token_out.lower() == "0x0000000000000000000000000000000000000000":
                token_out = WKITE_TOKEN_ADDRESS
            
            return abi_encode(
                ["uint8", "uint8", "uint256", "uint256", "address", "address", "address"],
                [32, 96, amount_out_wei, amount_out_min_wei, 
                 "0x0000000000000000000000000000000000000002",
                 self.web3.web3.to_checksum_address(token_in),
                 self.web3.web3.to_checksum_address(token_out)]
            )
        except Exception as e:
            logger.error(f"{self.account_index} | Error encoding trade bytes: {e}")
            raise

    async def build_swap_instructions(self, receiver: str, is_native_to_erc20: bool, 
                                    token_in: str, token_out: str, amount_out_wei: int, amount_out_min_wei: int) -> tuple:
        """Build swap instructions for the swap transaction"""
        try:
            trade_bytes = await self.encode_trade_bytes(token_in, token_out, amount_out_wei, amount_out_min_wei)
            
            hop = (
                3,  # action
                2_620_000,  # requiredGasLimit
                2_120_000,  # recipientGasLimit
                trade_bytes,  # trade bytes
                (  # bridgePath
                    "0x0000000000000000000000000000000000000000",  # bridgeSourceChain
                    False,  # sourceBridgeIsNative
                    "0x0000000000000000000000000000000000000000",  # bridgeDestinationChain
                    KITE_SWAP_ROUTER_ADDRESS,  # cellDestinationChain
                    DESTINATION_BLOCKCHAIN_ID,  # destinationBlockchainID
                    0,  # teleporterFee
                    0   # secondaryTeleporterFee
                )
            )
            
            return (
                1,  # sourceId
                self.web3.web3.to_checksum_address(receiver),  # receiver
                not is_native_to_erc20,  # payableReceiver
                self.web3.web3.to_checksum_address(receiver),  # rollbackReceiver
                0,  # rollbackTeleporterFee
                500_000,  # rollbackGasLimit
                [hop],  # hops[]
            )
        except Exception as e:
            logger.error(f"{self.account_index} | Error building swap instructions: {e}")
            raise

    @retry_async(default_value=False)
    async def perform_swap(self, token_in: str, token_out: str, amount_in: float, slippage: float = 3.0) -> bool:
        """Perform a token swap"""
        try:
            logger.info(f"{self.account_index} | Starting swap of {amount_in} from {token_in} to {token_out}")
            
            # Calculate output amounts
            price_data = await self.calculate_price(token_in, token_out, amount_in)
            if not price_data:
                raise Exception("Failed to calculate swap price")
            
            price, amount_out, token0, token1 = price_data
            amount_out_min = amount_out * (100 - slippage) / 100
            
            # Convert to wei
            amount_in_wei = self.web3.convert_to_wei(amount_in, 18)
            amount_out_wei = self.web3.convert_to_wei(amount_out, 18)
            amount_out_min_wei = self.web3.convert_to_wei(amount_out_min, 18)
            
            logger.info(f"{self.account_index} | Swapping {amount_in:.6f} tokens for ~{amount_out:.6f} tokens (min: {amount_out_min:.6f})")
            
            # Check if we're swapping from native token
            is_native_in = token_in.lower() == "0x0000000000000000000000000000000000000000"
            
            # Build transaction
            swap_contract = self.web3.web3.eth.contract(
                address=KITE_SWAP_ROUTER_ADDRESS,
                abi=SWAP_BRIDGE_ABI
            )
            
            instructions = await self.build_swap_instructions(
                receiver=self.wallet.address,
                is_native_to_erc20=is_native_in,
                token_in=token_in,
                token_out=token_out,
                amount_out_wei=amount_out_wei,
                amount_out_min_wei=amount_out_min_wei
            )
            
            # Handle token approval for ERC20 tokens
            if not is_native_in:
                approval_result = await self.web3.approve_token(
                    token_address=token_in,
                    spender_address=KITE_SWAP_ROUTER_ADDRESS,
                    amount=amount_in_wei,
                    wallet=self.wallet,
                    chain_id=await self.web3.web3.eth.chain_id,
                    token_abi=SWAP_BRIDGE_ABI,
                    explorer_url=EXPLORER_URL_KITEAI
                )
                if approval_result is None:
                    raise Exception("Token approval failed")
                
                await asyncio.sleep(random.randint(2, 5))
            
            # Build transaction using build_transaction
            chain_id = await self.web3.web3.eth.chain_id
            nonce = await self.web3.web3.eth.get_transaction_count(self.wallet.address)
            gas_params = await self.web3.get_gas_params()
            
            tx_data = await swap_contract.functions.initiate(
                token_in, amount_in_wei, instructions
            ).build_transaction({
                "from": self.wallet.address,
                "chainId": chain_id,
                "nonce": nonce,
                "value": amount_in_wei if is_native_in else 0,
                **gas_params,
            })
            
            # Execute transaction
            tx_hash = await self.web3.execute_transaction(
                tx_data=tx_data,
                wallet=self.wallet,
                chain_id=await self.web3.web3.eth.chain_id,
                explorer_url=EXPLORER_URL_KITEAI
            )
            
            if tx_hash:
                logger.success(f"{self.account_index} | Swap successful! TX: {EXPLORER_URL_KITEAI}{tx_hash}")
                return True
            else:
                raise Exception("Swap failed")
                
        except Exception as e:
            logger.error(f"{self.account_index} | Swap error: {e}")
            raise

    @retry_async(default_value=False)
    async def bridge_tokens(self, token_address: str, dest_chain_id: int, amount: float) -> bool:
        """Bridge tokens to another chain"""
        try:
            logger.info(f"{self.account_index} | Starting bridge of {amount} tokens to chain {dest_chain_id}")
            
            is_native = token_address.lower() == "0x0000000000000000000000000000000000000000"
            amount_wei = self.web3.convert_to_wei(amount, 18)
            
            # Choose the appropriate bridge router
            bridge_address = KITE_BRIDGE_ROUTER_ADDRESS if is_native else BRIDGE_ROUTER_ADDRESS
            
            bridge_contract = self.web3.web3.eth.contract(
                address=bridge_address,
                abi=SWAP_BRIDGE_ABI
            )
            
            # Handle token approval for ERC20 tokens
            if not is_native:
                approval_result = await self.web3.approve_token(
                    token_address=token_address,
                    spender_address=bridge_address,
                    amount=amount_wei,
                    wallet=self.wallet,
                    chain_id=await self.web3.web3.eth.chain_id,
                    token_abi=SWAP_BRIDGE_ABI,
                    explorer_url=EXPLORER_URL_KITEAI
                )
                if approval_result is None:
                    logger.error(f"{self.account_index} | Token approval failed for bridge")
                    return False
                
                await asyncio.sleep(random.randint(2, 5))
            
            # Build transaction using build_transaction
            chain_id = await self.web3.web3.eth.chain_id
            nonce = await self.web3.web3.eth.get_transaction_count(self.wallet.address)
            gas_params = await self.web3.get_gas_params()
            
            tx_data = await bridge_contract.functions.send(
                dest_chain_id, self.wallet.address, amount_wei
            ).build_transaction({
                "from": self.wallet.address,
                "chainId": chain_id,
                "nonce": nonce,
                "value": amount_wei if is_native else 0,
                **gas_params,
            })
            
            # Execute transaction
            tx_hash = await self.web3.execute_transaction(
                tx_data=tx_data,
                wallet=self.wallet,
                chain_id=await self.web3.web3.eth.chain_id,
                explorer_url=EXPLORER_URL_KITEAI
            )
            
            if tx_hash:
                logger.success(f"{self.account_index} | Bridge successful! TX: {EXPLORER_URL_KITEAI}{tx_hash}")
                return True
            else:
                logger.error(f"{self.account_index} | Bridge failed")
                return False
                
        except Exception as e:
            logger.error(f"{self.account_index} | Bridge error: {e}")
            return False

    @retry_async(default_value=None)
    async def check_bridge_interaction(self) -> Optional[bool]:
        """Check if the wallet has interacted with the bridge before"""
        try:
            headers = {
                'origin': 'https://bridge.prod.gokite.ai',
                'priority': 'u=1, i',
                'referer': 'https://bridge.prod.gokite.ai/',
            }

            params = {
                'address': self.wallet.address,
            }

            response = await self.session.get(
                url='https://bridge-backend.prod.gokite.ai/check-interaction',
                params=params,
                headers=headers
            )

            result = response.json()
            return result.get('data', {}).get('has_interacted', False)
            
        except Exception as e:
            logger.error(f"{self.account_index} | Error checking bridge interaction: {e}")
            return None

    async def get_current_balances(self) -> dict:
        """Get current balances for all supported tokens"""
        try:
            balances = {}
            
            # Native token (KITE)
            native_balance = await self.get_token_balance("0x0000000000000000000000000000000000000000")
            if native_balance:
                balances["KITE"] = native_balance
            
            # USDT token
            usdt_balance = await self.get_token_balance(USDT_TOKEN_ADDRESS)
            if usdt_balance:
                balances["USDT"] = usdt_balance
                
            return balances
            
        except Exception as e:
            logger.error(f"{self.account_index} | Error getting current balances: {e}")
            return {}

    @retry_async(default_value=False)
    async def auto_swap(self) -> bool:
        """Automatically perform a random swap based on available balances"""
        try:
            logger.info(f"{self.account_index} | Starting auto swap")
            
            # Get current balances
            balances = await self.get_current_balances()
            if not balances:
                logger.warning(f"{self.account_index} | No balances found")
                return False
            
            # Filter tokens with balance > 0
            available_tokens = {name: balance for name, balance in balances.items() if balance.formatted > 0}
            
            if len(available_tokens) < 1:
                logger.warning(f"{self.account_index} | No tokens with balance found")
                return False
            
            # Choose random token to swap from
            token_names = list(available_tokens.keys())
            from_token_name = random.choice(token_names)
            from_balance = available_tokens[from_token_name]
            
            # Define token addresses
            token_addresses = {
                "KITE": "0x0000000000000000000000000000000000000000",
                "USDT": USDT_TOKEN_ADDRESS
            }
            
            # Choose random token to swap to (different from from_token)
            available_to_tokens = [name for name in token_addresses.keys() if name != from_token_name]
            if not available_to_tokens:
                logger.warning(f"{self.account_index} | No available tokens to swap to")
                return False
            
            to_token_name = random.choice(available_to_tokens)
            
            # Calculate swap amount (random percentage of balance)
            swap_percentage = random.uniform(
                self.config.STAKINGS.GOKITE.KITE_AMOUNT_TO_STAKE[0] / 100,  # Using existing config as reference
                self.config.STAKINGS.GOKITE.KITE_AMOUNT_TO_STAKE[1] / 100
            )
            swap_amount = float(from_balance.formatted) * swap_percentage
            
            # Minimum swap amount check
            if swap_amount < 0.0001:
                logger.warning(f"{self.account_index} | Swap amount too small: {swap_amount}")
                return False
            
            logger.info(f"{self.account_index} | Swapping {swap_amount:.6f} {from_token_name} to {to_token_name}")
            
            return await self.perform_swap(
                token_in=token_addresses[from_token_name],
                token_out=token_addresses[to_token_name],
                amount_in=swap_amount,
                slippage=3.0
            )
            
        except Exception as e:
            logger.error(f"{self.account_index} | Auto swap error: {e}")
            return False

    @retry_async(default_value=False)
    async def auto_bridge(self) -> bool:
        """Automatically bridge tokens to Base Sepolia"""
        try:
            logger.info(f"{self.account_index} | Starting auto bridge")
            
            # Get current balances
            balances = await self.get_current_balances()
            if not balances:
                logger.warning(f"{self.account_index} | No balances found")
                return False
            
            # Filter tokens with balance > 0
            available_tokens = {name: balance for name, balance in balances.items() if balance.formatted > 0}
            
            if len(available_tokens) < 1:
                logger.warning(f"{self.account_index} | No tokens with balance found")
                return False
            
            # Choose random token to bridge
            token_names = list(available_tokens.keys())
            token_name = random.choice(token_names)
            token_balance = available_tokens[token_name]
            
            # Calculate bridge amount (random percentage of balance)
            bridge_percentage = random.uniform(0.1, 0.3)  # Bridge 10-30% of balance
            bridge_amount = float(token_balance.formatted) * bridge_percentage
            
            # Minimum bridge amount check
            if bridge_amount < 0.0001:
                logger.warning(f"{self.account_index} | Bridge amount too small: {bridge_amount}")
                return False
            
            # Define token address
            token_address = "0x0000000000000000000000000000000000000000" if token_name == "KITE" else USDT_TOKEN_ADDRESS
            
            logger.info(f"{self.account_index} | Bridging {bridge_amount:.6f} {token_name} to Base Sepolia")
            
            return await self.bridge_tokens(
                token_address=token_address,
                dest_chain_id=BASE_SEPOLIA_CHAIN_ID,
                amount=bridge_amount
            )
            
        except Exception as e:
            logger.error(f"{self.account_index} | Auto bridge error: {e}")
            return False
