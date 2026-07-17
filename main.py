import asyncio
from concurrent.futures import ThreadPoolExecutor

from rocketride import RocketRideClient
from rocketride.schema import Question

_input_executor = ThreadPoolExecutor(max_workers=1)


async def async_input(prompt: str = "") -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_input_executor, input, prompt)


async def main():
    async with RocketRideClient() as client:
        result = await client.use(filepath="pipelines/chat.pipe", use_existing=True)
        token = result["token"]
        print(f"Connected. Pipeline token: {token}")
        print("Type a question and press Enter (or 'quit' to exit).\n")

        while True:
            user_input = await async_input("You: ")
            if user_input.strip().lower() in ("quit", "exit"):
                break
            if not user_input.strip():
                continue

            question = Question()
            question.addQuestion(user_input)

            response = await client.chat(token=token, question=question)
            answers = response.get("answers", [])
            print(f"Agent: {answers[0] if answers else response}\n")


if __name__ == "__main__":
    asyncio.run(main())
