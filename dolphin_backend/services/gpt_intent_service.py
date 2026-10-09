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
            timeout=30.0,  # ⚡ Prevent indefinite hangs
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
                            "GREETING – greetings like hi, hello, good morning, hey, introductions (I am X, my name is X, this is X)\n"
                            "GOODBYE – bye, see you, log off, signing off\n"
                            "THANK – thanking or appreciation messages\n"
                            "WELL_WISH – how are you, hope you are well, how are you feeling\n"
                            "NEGATIVE – dissatisfaction, complaints, discouraging statements (NOT workplace safety questions - those are QUERY)\n"
                            "THREATENING – harsh, abusive, threatening, or aggressive commands\n"
                            "OFF_TOPIC – questions, coding, or topics completely unrelated to maritime/marine education (e.g., Python/Java/software programming, recipes, cooking, sports, cinema, entertainment, politics, non-marine general knowledge)\n"
                            "QUERY – genuine questions or information-seeking messages about marine topics, seafaring, navigation, marine engineering, ship operations, maritime safety, workplace safety, crew management, harassment, bullying, intoxication, or operational procedures\n\n"
                            "IMPORTANT: Messages like 'I am [name]', 'My name is [name]', 'This is [name]' are GREETING (user introductions).\n\n"
                            "Rules:\n"
                            "- Return ONLY the category name (one word)\n"
                            "- Do NOT explain or add anything else\n"
                            "- Choose the closest matching intent\n"
                            "- When in doubt between GREETING and QUERY, choose GREETING if it's an introduction\n"
                            "- If the question is about non-marine topics like programming (e.g., 'what is python', 'how to code in C'), movies, sports, cooking, politics, classify as OFF_TOPIC\n"
                            "- Workplace safety questions (harassment, bullying, intoxication, crew incidents) are always QUERY, NOT NEGATIVE\n"
                            "- Questions asking for advice or how to handle maritime situations are QUERY\n"
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
                "NEGATIVE", "THREATENING", "OFF_TOPIC", "QUERY"
            }

            if classification not in valid_categories:
                logger.warning(f"[GPT INTENT] Invalid classification '{classification}', defaulting to QUERY")
                return "QUERY"

            return classification

        except Exception as e:
            logger.error(f"GPT intent classification failed: {e}")
            return "QUERY"