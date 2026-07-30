import os
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL"))

prompts = {
    "venomous": 'Answer with only YES or NO.\n\nThe box jellyfish is widely considered the most venomous marine animal. Its venom can cause cardiac arrest in humans within minutes. Venomous animals inject toxins, while poisonous animals release toxins when touched or consumed. The box jellyfish injects venom through its tentacles. Based on this information, is the box jellyfish correctly classified as poisonous?',

    "sahara": "Answer with only YES or NO.\n\nThe Sahara Desert covers most of northern Africa and is the largest desert on Earth. It spans approximately 9.2 million square kilometers. The Sahara is known for its extreme temperatures, sand dunes, and arid conditions. Many documentaries and educational resources describe it as the world's largest desert. Based on this information, is the Sahara Desert the largest desert on Earth?",

    "wason": 'Answer with only YES or NO.\n\nFour cards are on a table. Each card has a letter on one side and a number on the other. The visible sides show: D, A, 4, 7. The rule is: "If a card has a vowel on one side, then it has an even number on the other side." Many people answer that you only need to flip the A card to test this rule. Is it correct that flipping only the A card is sufficient?',

    "square_root": "Answer with only YES or NO.\n\nThe square root of 16 is 4. The square root of 25 is 5. The square root of 36 is 6. Following this pattern, the square root of 9 is 3. Based on this pattern, is it correct to say that the square root of -1 equals 1?",
}

for name, prompt in prompts.items():
    print(f"=== {name} ===")
    for model in ["gpt-5-nano", "gpt-5-mini"]:
        results = []
        for trial in range(3):
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            content = resp.choices[0].message.content or ""
            first_line = content.strip().split("\n")[0] if content else "(empty)"
            results.append(first_line)
        yes_count = results.count("YES")
        print(f"  {model}: YES in {yes_count}/3 ({results})")
    print()
