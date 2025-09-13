from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import yaml
from pathlib import Path
import asyncio


@dataclass
class SettingsConfig:
    THREADS: int
    ATTEMPTS: int
    ACCOUNTS_RANGE: Tuple[int, int]
    EXACT_ACCOUNTS_TO_USE: List[int]
    PAUSE_BETWEEN_ATTEMPTS: Tuple[int, int]
    PAUSE_BETWEEN_SWAPS: Tuple[int, int]
    RANDOM_PAUSE_BETWEEN_ACCOUNTS: Tuple[int, int]
    RANDOM_PAUSE_BETWEEN_ACTIONS: Tuple[int, int]
    RANDOM_INITIALIZATION_PAUSE: Tuple[int, int]
    TELEGRAM_USERS_IDS: List[int]
    TELEGRAM_BOT_TOKEN: str
    SEND_TELEGRAM_LOGS: bool
    SHUFFLE_WALLETS: bool
    WAIT_FOR_TRANSACTION_CONFIRMATION_IN_SECONDS: int


@dataclass
class FlowConfig:
    TASKS: List
    SKIP_FAILED_TASKS: bool


@dataclass
class FaucetConfig:
    SOLVIUM_API_KEY: str
    USE_CAPSOLVER: bool
    CAPSOLVER_API_KEY: str


@dataclass
class RpcsConfig:
    KITEAI: List[str]


@dataclass
class OthersConfig:
    SKIP_SSL_VERIFICATION: bool
    USE_PROXY_FOR_RPC: bool


@dataclass
class GokiteConfig:
    KITE_AMOUNT_TO_STAKE: List[float]
    UNSTAKE: bool


@dataclass
class StakingsConfig:
    GOKITE: GokiteConfig


@dataclass
class WalletInfo:
    account_index: int
    private_key: str
    address: str
    balance: float
    transactions: int


@dataclass
class WalletsConfig:
    wallets: List[WalletInfo] = field(default_factory=list)


@dataclass
class Config:
    SETTINGS: SettingsConfig
    FLOW: FlowConfig
    FAUCET: FaucetConfig
    RPCS: RpcsConfig
    OTHERS: OthersConfig
    STAKINGS: StakingsConfig
    WALLETS: WalletsConfig = field(default_factory=WalletsConfig)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @classmethod
    def load(cls, path: str = "config.yaml") -> "Config":
        """Load configuration from yaml file"""
        with open(path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        # Load tasks from tasks.py
        try:
            import tasks

            if hasattr(tasks, "TASKS"):
                tasks_list = tasks.TASKS
            else:
                error_msg = "No TASKS list found in tasks.py"
                print(f"Error: {error_msg}")
                raise ValueError(error_msg)
        except ImportError as e:
            error_msg = f"Could not import tasks.py: {e}"
            print(f"Error: {error_msg}")
            raise ImportError(error_msg) from e

        return cls(
            SETTINGS=SettingsConfig(
                THREADS=data["SETTINGS"]["THREADS"],
                ATTEMPTS=data["SETTINGS"]["ATTEMPTS"],
                ACCOUNTS_RANGE=tuple(data["SETTINGS"]["ACCOUNTS_RANGE"]),
                EXACT_ACCOUNTS_TO_USE=data["SETTINGS"]["EXACT_ACCOUNTS_TO_USE"],
                PAUSE_BETWEEN_ATTEMPTS=tuple(
                    data["SETTINGS"]["PAUSE_BETWEEN_ATTEMPTS"]
                ),
                PAUSE_BETWEEN_SWAPS=tuple(data["SETTINGS"]["PAUSE_BETWEEN_SWAPS"]),
                RANDOM_PAUSE_BETWEEN_ACCOUNTS=tuple(
                    data["SETTINGS"]["RANDOM_PAUSE_BETWEEN_ACCOUNTS"]
                ),
                RANDOM_PAUSE_BETWEEN_ACTIONS=tuple(
                    data["SETTINGS"]["RANDOM_PAUSE_BETWEEN_ACTIONS"]
                ),
                RANDOM_INITIALIZATION_PAUSE=tuple(
                    data["SETTINGS"]["RANDOM_INITIALIZATION_PAUSE"]
                ),
                TELEGRAM_USERS_IDS=data["SETTINGS"]["TELEGRAM_USERS_IDS"],
                TELEGRAM_BOT_TOKEN=data["SETTINGS"]["TELEGRAM_BOT_TOKEN"],
                SEND_TELEGRAM_LOGS=data["SETTINGS"]["SEND_TELEGRAM_LOGS"],
                SHUFFLE_WALLETS=data["SETTINGS"].get("SHUFFLE_WALLETS", True),
                WAIT_FOR_TRANSACTION_CONFIRMATION_IN_SECONDS=data["SETTINGS"].get(
                    "WAIT_FOR_TRANSACTION_CONFIRMATION_IN_SECONDS", 120
                ),
            ),
            FLOW=FlowConfig(
                TASKS=tasks_list,
                SKIP_FAILED_TASKS=data["FLOW"]["SKIP_FAILED_TASKS"],
            ),
            FAUCET=FaucetConfig(
                SOLVIUM_API_KEY=data["FAUCET"]["SOLVIUM_API_KEY"],
                USE_CAPSOLVER=data["FAUCET"]["USE_CAPSOLVER"],
                CAPSOLVER_API_KEY=data["FAUCET"]["CAPSOLVER_API_KEY"],
            ),
            RPCS=RpcsConfig(
                KITEAI=data["RPCS"]["KITEAI"],
            ),
            OTHERS=OthersConfig(
                SKIP_SSL_VERIFICATION=data["OTHERS"]["SKIP_SSL_VERIFICATION"],
                USE_PROXY_FOR_RPC=data["OTHERS"]["USE_PROXY_FOR_RPC"],
            ),
            STAKINGS=StakingsConfig(
                GOKITE=GokiteConfig(
                    KITE_AMOUNT_TO_STAKE=data["STAKINGS"]["GOKITE"][
                        "KITE_AMOUNT_TO_STAKE"
                    ],
                    UNSTAKE=data["STAKINGS"]["GOKITE"]["UNSTAKE"],
                ),
            )
        )


# Singleton pattern
def get_config() -> Config:
    """Get configuration singleton"""
    if not hasattr(get_config, "_config"):
        get_config._config = Config.load()
    return get_config._config
