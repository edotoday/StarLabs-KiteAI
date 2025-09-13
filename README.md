# StarLabs KiteAI Bot 🚀

<div align="center">

[![Telegram Channel](https://img.shields.io/badge/Telegram-Channel-blue?style=for-the-badge&logo=telegram)](https://t.me/StarLabsTech)
[![Telegram Chat](https://img.shields.io/badge/Telegram-Chat-blue?style=for-the-badge&logo=telegram)](https://t.me/StarLabsChat)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-black?style=for-the-badge&logo=github)](https://github.com/0xStarLabs)

</div>

A powerful automation tool for KiteAI Ozone platform with advanced task management, AI interactions, token operations, and social integrations.

## 🌟 Features

### Core Functionality
- ✨ **Multi-threaded processing** - Run multiple accounts simultaneously
- 🔄 **Automatic retries** with configurable attempts
- 🔐 **Proxy support** for enhanced security
- 📊 **Account range selection** and exact account filtering
- 🎲 **Random pauses** between operations
- 🔔 **Telegram logging** integration
- 📝 **Database task tracking** with SQLite storage
- 🧩 **Modular task system** with flexible configurations

### KiteAI Platform Operations
- **Account Management**:
  - Login and authentication via EOA address
  - Account registration and profile management
  - Badge minting and collection
  - Balance tracking (KITE and USDT)

- **AI Ozone Interactions**:
  - Multi-agent AI conversations
  - Automated question generation
  - Receipt submission and transaction processing
  - Support for multiple AI agents (Sherlock, etc.)

- **Token Operations**:
  - DEX swaps between KITE/USDT tokens
  - Cross-chain bridging to Base Sepolia
  - Automated balance management
  - Slippage protection and price calculation

- **Social Integrations**:
  - Twitter/X account connection
  - Discord account linking
  - Automated social verification

- **Faucet & Rewards**:
  - Multi-faucet token claiming
  - Captcha solving (Solvium/Capsolver)
  - Staking operations with flexible amounts
  - Daily quiz completion

- **Quests & Tasks**:
  - Onboarding quiz automation
  - Daily quest completion
  - Badge eligibility checking
  - XP point tracking

## 📋 Requirements

- Python 3.11.x
- Private keys for Ethereum wallets
- Proxies for enhanced security
- Solvium or Capsolver API key for captcha solving
- (Optional) Telegram bot token for logging
- (Optional) Discord and Twitter tokens for social linking

## 🚀 Installation

1. Clone the repository:
```bash
git clone https://github.com/0xStarLabs/StarLabs-KiteAI.git
cd StarLabs-KiteAI
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your settings in `config.yaml`
4. Add your private keys to `data/private_keys.txt`
5. (Optional) Add proxies to `data/proxies.txt`
6. (Optional) Add Discord tokens to `data/discord_tokens.txt`
7. (Optional) Add Twitter tokens to `data/twitter_tokens.txt`

## 📁 Project Structure

```
StarLabs-KiteAI/
├── data/
│   ├── accounts.db            # SQLite database for task tracking
│   ├── private_keys.txt       # Ethereum wallet private keys
│   ├── proxies.txt           # Proxy addresses (optional)
│   ├── discord_tokens.txt    # Discord tokens (optional)
│   └── twitter_tokens.txt    # Twitter tokens (optional)
├── src/
│   ├── model/
│   │   ├── database/         # Database management
│   │   ├── kiteai/          # KiteAI platform integration
│   │   ├── onchain/         # Blockchain operations
│   │   └── help/            # Helper modules (captcha, stats)
│   └── utils/               # Utility functions and configurations
├── config.yaml             # Main configuration file
└── tasks.py                # Task definitions
```

## 📝 Configuration

### 1. Data Files
- `private_keys.txt`: One private key per line
- `proxies.txt`: One proxy per line (format: `http://user:pass@ip:port`)
- `discord_tokens.txt`: Discord authorization tokens (optional)
- `twitter_tokens.txt`: Twitter auth tokens (optional)

### 2. Main Settings (`config.yaml`)
```yaml
SETTINGS:
  THREADS: 1                      # Number of parallel threads
  ATTEMPTS: 5                     # Retry attempts for failed actions
  ACCOUNTS_RANGE: [0, 0]          # Wallet range to use (default: all)
  EXACT_ACCOUNTS_TO_USE: []       # Specific wallets to use (default: all)
  SHUFFLE_WALLETS: true           # Randomize wallet processing order
  PAUSE_BETWEEN_ATTEMPTS: [3, 10] # Random pause between retries
  PAUSE_BETWEEN_SWAPS: [5, 30]    # Random pause between operations

FAUCET:
  SOLVIUM_API_KEY: "your_key"     # Cheapest captcha solver
  USE_CAPSOLVER: false            # Alternative captcha solver
  CAPSOLVER_API_KEY: "your_key"   # Capsolver API key

STAKINGS:
  GOKITE:
    KITE_AMOUNT_TO_STAKE: [1, 2]  # Amount range to stake
    UNSTAKE: false                # Enable unstaking (not implemented)
```

### 3. Web Configuration Interface
Launch the browser-based configuration editor:
```bash
python -c "from src.utils.config_browser import run; run()"
```
Access at: `http://127.0.0.1:3456`

## 🎮 Usage

### Database Management
Before running tasks, set up the database:
```bash
python -c "from src.model.database.db_manager import show_database_menu; import asyncio; asyncio.run(show_database_menu())"
```

Database options:
- **Create/Reset Database** - Initialize new database with tasks
- **Generate Tasks for Completed Wallets** - Add new tasks to finished wallets
- **Show Database Contents** - View current database status
- **Regenerate Tasks for All** - Reset all wallet tasks
- **Add New Wallets** - Import wallets from files

### Task Configuration
Edit `tasks.py` to select which modules to run:

```python
# Example task configurations
DAILY_ROUTINE = [
    "login",
    "complete_quiz", 
    "faucet",
    ("connect_socials", "ozone_ai_chat"),  # Run both in random order
    ["stake", "perform_swap"],             # Choose one randomly
]

FULL_AUTOMATION = [
    "login",
    "complete_quiz",
    "connect_socials", 
    "ozone_ai_chat",
    "faucet",
    "mint_badges",
    "stake",
    "perform_swap",
    "perform_bridge"
]
```

### Run the Bot
```bash
python main.py
```

## 🔧 Available Operations

### Core KiteAI Operations
- **`login`** - Authenticate with KiteAI platform
- **`complete_quiz`** - Complete onboarding and daily quizzes
- **`faucet`** - Claim tokens from multiple faucets
- **`get_balance`** - Check KITE and USDT balances
- **`mint_badges`** - Claim available badges

### Social & AI Operations  
- **`connect_socials`** - Link Twitter and Discord accounts
- **`ozone_ai_chat`** - Interact with AI agents for rewards

### Token Operations
- **`stake`** - Stake KITE tokens in subnets
- **`perform_swap`** - Swap between KITE and USDT
- **`perform_bridge`** - Bridge tokens to Base Sepolia
- **`check_bridge_status`** - Verify bridge interaction history

### Advanced Features
- **Auto-retry mechanisms** with exponential backoff
- **Balance-based swap amounts** with percentage calculations
- **Multi-agent AI conversations** with random selection
- **Social account verification** with OAuth flows
- **Cross-chain bridge detection** and automation

## 🔍 Task Flow Examples

### Simple Daily Tasks
```python
DAILY_TASKS = [
    "login",           # Authenticate
    "faucet",          # Claim daily tokens  
    "complete_quiz",   # Complete daily quiz
    "ozone_ai_chat"    # AI interaction for rewards
]
```

### Advanced Trading Flow
```python
TRADING_FLOW = [
    "login",
    "get_balance", 
    "perform_swap",    # KITE → USDT
    "perform_swap",    # USDT → KITE  
    "stake",           # Stake earned tokens
    "perform_bridge"   # Bridge to other chains
]

### Social Integration Flow  
```python
SOCIAL_SETUP = [
    "login",
    "connect_socials", # Link social accounts
    "mint_badges",     # Claim social badges
    "ozone_ai_chat"    # AI conversations
]
```

## 📊 Database Features

### Task Tracking
- **SQLite database** for persistent task storage
- **Batch operations** for improved performance
- **Status tracking** (pending/completed) per task
- **Progress monitoring** with detailed statistics

### Wallet Management
- **Individual task queues** per wallet
- **Proxy assignment** and rotation
- **Completion status** tracking
- **Dynamic task generation** from configuration

## 🔐 Security Features

- **Proxy support** for all operations
- **SSL verification** control
- **Rate limiting** protection
- **Error handling** with retry mechanisms
- **Secure token storage** and management

## ⚠️ Important Notes

1. **Captcha Requirements**: Some operations require captcha solving
2. **Rate Limits**: Respect platform rate limits to avoid bans
3. **Token Management**: Ensure sufficient balance for operations
4. **Proxy Quality**: Use high-quality proxies for stability
5. **Configuration**: Test with small account ranges first

## 📜 License
MIT License

## ⚠️ Disclaimer
This tool is for educational and research purposes only. Use at your own risk and in accordance with KiteAI's terms of service. Always respect platform rate limits and guidelines.

## 🔗 Links
- [KiteAI Platform](https://testnet.gokite.ai)
- [Solvium Captcha Solver](https://t.me/solvium_crypto_bot)

## 🆘 Support
For support and updates, join our community or submit issues on GitHub.