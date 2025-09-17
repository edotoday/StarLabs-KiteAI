TASKS = ["ACCOUNT_INFO"]

EVERYTHING = ["complete_quiz", "faucet", "faucet_onchain", "ozone_staking", "claim_badges", "ozone_ai_chat", "tesseract_swaps", "kite_bridge"]

ACCOUNT_INFO = ["account_info"]
FAUCET = ["faucet"]
FAUCET_ONCHAIN = ["faucet_onchain"]
CONNECT_SOCIALS = ["connect_socials"]
COMPLETE_QUIZ = ["complete_quiz"]
OZONE_STAKING = ["ozone_staking"]
CLAIM_BADGES = ["claim_badges"]
OZONE_AI_CHAT = ["ozone_ai_chat"]
TESSERACT_SWAPS = ["tesseract_swaps"]
KITE_BRIDGE = ["kite_bridge"]
"""
EN:
You can create your own task with the modules you need 
and add it to the TASKS list or use our ready-made preset tasks.

( ) - Means that all of the modules inside the brackets will be executed 
in random order
[ ] - Means that only one of the modules inside the brackets will be executed 
on random
SEE THE EXAMPLE BELOW:

RU:
Вы можете создать свою задачу с модулями, которые вам нужны, 
и добавить ее в список TASKS, см. пример ниже:

( ) - означает, что все модули внутри скобок будут выполнены в случайном порядке
[ ] - означает, что будет выполнен только один из модулей внутри скобок в случайном порядке
СМОТРИТЕ ПРИМЕР НИЖЕ:

CHINESE:
你可以创建自己的任务，使用你需要的模块，
并将其添加到TASKS列表中，请参见下面的示例：

( ) - 表示括号内的所有模块将按随机顺序执行
[ ] - 表示括号内的模块将按随机顺序执行

--------------------------------
!!! IMPORTANT !!!
EXAMPLE | ПРИМЕР | 示例:

TASKS = [
    "CREATE_YOUR_OWN_TASK",
]
CREATE_YOUR_OWN_TASK = [
    "faucet",
    ("faucet_tokens", "swaps"),
    ["storagescan_deploy", "conft_mint"],
    "swaps",
]
--------------------------------


BELOW ARE THE READY-MADE TASKS THAT YOU CAN USE:
СНИЗУ ПРИВЕДЕНЫ ГОТОВЫЕ ПРИМЕРЫ ЗАДАЧ, КОТОРЫЕ ВЫ МОЖЕТЕ ИСПОЛЬЗОВАТЬ:
以下是您可以使用的现成任务：


faucet - faucet kite tokens (needs captcha)
faucet_onchain - faucet kite tokens onchain
connect_socials - connect socials
"""
