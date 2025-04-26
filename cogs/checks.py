# a whole bunch of checks for automod

# FUNCTION SIGNATURE: (content: str, clean_content: str, channel_id: int) -> list[bool | WarnReason]

from emoji import emoji_count
from enum import Enum
import re, unicodedata, os

EMOJI_LIMIT = 6

BANNED_WORDS = []

WORD_BYPASSES = {
    "0": [
        "o"
    ],
    "1": [
        "i"
    ],
    "2": [
        "z"
    ],
    "3": [
        "m",
        "w",
        "e"
    ],
    "4": [
        "h",
        "y",
        "a"
    ],
    "5": [
        "s"
    ],
    "6": [
        "g",
        "b"
    ],
    "7": [
        "t"
    ],
    "8": [
        "x",
        "b"
    ],
    "9": [
        "g",
        "j",
        "p"
    ],
    "_": [
        ""
    ],
    "*": [
        ""
    ]
}

with open("banned-words.txt", "r") as f:
    BANNED_WORDS = f.read().strip().split("\n")

class WarnReason(Enum):
    DISCORD_LINK = 1
    ZALGO = 2
    BANNED_WORD = 3
    EMOJI = 4

async def emoji_check(content: str, clean_content: str, channel_id: int) -> tuple[bool, WarnReason]:
    # thank you ChatGPT for the RegeX ^_^
    return (emoji_count(content) + len(re.findall(r'<[^:<>]*:[^:<>]*:[^:<>]*>', content)) > EMOJI_LIMIT, WarnReason.EMOJI)

async def banned_word_raw(content: str, clean_content: str, channel_id: int) -> tuple[bool, WarnReason]:
    content = content.lower()
    contains = False
    for word in content.split(" "):
        if word in BANNED_WORDS:
            contains = True
            break

    return (contains, WarnReason.BANNED_WORD)

async def banned_word_punctuation(content: str, clean_content: str, channel_id: int) -> tuple[bool, WarnReason]:
    for punctuation in "!@#$%^&*()-=[]\\;',./_+{}|:\"<>?":
        content = content.replace(punctuation, "")
    
    return await banned_word_raw(content, clean_content, channel_id)

async def banned_word_normalization(content: str, clean_content: str, channel_id: int) -> tuple[bool, WarnReason]:
    content = unicodedata.normalize("NFKC", content)
    return await banned_word_raw(content, clean_content, channel_id)

async def banned_word_bypasses(content: str, clean_content: str, channel_id: int) -> tuple[bool, WarnReason]:
    contains = False
    for being_replaced in WORD_BYPASSES.keys():
        for replacer in WORD_BYPASSES[being_replaced]:
            new_content = content.replace(being_replaced, replacer)
            check = await banned_word_raw(new_content, new_content, channel_id)
            if check[0]:
                contains = True
                break
        
        if contains:
            break

    return (contains, WarnReason.BANNED_WORD)

def extract_invite_id(text):
    # Define regex pattern to match Discord invite links
    pattern = r'(?:https?://)?(?:www\.)?(?:discord\.(?:com|gg)/invite/|discord\.gg/)([a-zA-Z0-9]+)'
    # Search for the pattern in the input text
    match = re.search(pattern, text)
    if match:
        # Extract and return the invite ID
        return match.group(1)
    else:
        return None

async def advertisements(content: str, clean_content: str, channel_id: int) -> tuple[bool, WarnReason]:
    return (str(channel_id) != os.getenv("ADVERTS_CHANNEL") and extract_invite_id(content) is not None, WarnReason.DISCORD_LINK)
