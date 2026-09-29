from openai import AsyncOpenAI
from loguru import logger
from config import Settings


class GPTIntentService:
    """
    Classifies user intent using OpenAI LLM.
    
    ⚡ OPTIMIZATIONS (Latency Remediation):
    - Uses AsyncOpenAI instead of sync OpenAI (unblocks event loop)
    - Uses gpt-4o-mini instead of gpt-4-turbo (classification needs only ~10 tokens)
    - Saves ~2-4s per classification call (gpt-4o-mini responds in ~0.3-1s vs ~3-5s)
    - Added timeout=30.0 to prevent indefinite hangs
    """
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=Settings().openai_api_key,
            timeout=10.0,  # ⚡ Prevent hangs
        )

    async def classify_intent(self, message: str) -> str:
        try:
            # ⚡ OPTIMIZATION: Use gpt-4o-mini for classification
            # Classification only returns a single word (~10 tokens)
            # gpt-4o-mini responds in ~0.3-1s vs ~3-5s for gpt-4-turbo
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Classify the user message into EXACTLY one category.\n\n"
                            "Valid categories:\n"
                            "GREETING – greetings like hi, hello, good morning, hey, user introductions (I am X, my name is X), and bot identity inquiries (who are you, what can you do, tell me about yourself, what is dolphin ai)\n"
                            "GOODBYE – bye, see you, log off, signing off, farewell\n"
                            "THANK – thanking or appreciation messages (thanks, thank you, appreciate it)\n"
                            "WELL_WISH – well wishes and casual small-talk check-ins (how are you, are you doing, what are you doing, how are you doing, how is it going, how are things, hope you are well, how are you feeling, whats up)\n"
                            "OUT_OF_SCOPE – completely non-marine / unrelated questions or requests (e.g. cooking/recipes, programming/code, sports, celebrities, general math/science, movies, jokes, weather in non-marine context, general trivia)\n"
                            "NEGATIVE – dissatisfaction, complaints, discouraging statements (NOT workplace safety questions - those are QUERY)\n"
                            "THREATENING – harsh, abusive, threatening, or aggressive commands\n"
                            "QUERY – genuine maritime domain questions or information-seeking messages about marine topics, ships, navigation, engines, cargo, seamanship, SOLAS, MARPOL, ISM, SMS, SOPs, checklists, workplace safety, crew management, or operational procedures\n\n"
                            "IMPORTANT:\n"
                            "- Messages like 'I am [name]', 'My name is [name]', 'who are you', 'what can you do' are GREETING.\n"
                            "- Messages like 'are you doing', 'how are you doing', 'what are you doing' are WELL_WISH.\n"
                            "- Completely non-marine questions like 'how to cook pasta', 'write python code', 'who is elon musk', 'tell me a joke' are OUT_OF_SCOPE.\n\n"
                            "Rules:\n"
                            "- Return ONLY the category name (one word)\n"
                            "- Do NOT explain or add anything else\n"
                            "- Choose the closest matching intent\n"
                            "- When in doubt between GREETING/WELL_WISH and QUERY, choose GREETING/WELL_WISH if it's casual conversation\n"
                            "- Workplace safety questions (harassment, bullying, intoxication, crew incidents) are always QUERY, NOT NEGATIVE\n"
                            "- Questions asking for advice or how to handle situations in marine context are QUERY\n"
                        ),
                    },
                    {"role": "user", "content": message},
                ],
                temperature=0,
                max_tokens=10,  # Increased slightly to ensure full word
            )

            classification = response.choices[0].message.content.strip().upper()

            # ✅ Log for debugging
            logger.info(f"[GPT INTENT] '{message}' → {classification}")

            # ✅ Validate classification
            valid_categories = {
                "GREETING", "GOODBYE", "THANK", "WELL_WISH",
                "OUT_OF_SCOPE", "NEGATIVE", "THREATENING", "QUERY"
            }

            if classification not in valid_categories:
                logger.warning(f"[GPT INTENT] Invalid classification '{classification}', defaulting to QUERY")
                return "QUERY"

            return classification

        except Exception as e:
            logger.error(f"GPT intent classification failed: {e}")
            return "QUERY"
