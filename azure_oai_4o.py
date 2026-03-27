import argparse
import os

from dotenv import load_dotenv
from openai import AzureOpenAI


def build_client() -> AzureOpenAI:
	load_dotenv()

	api_key = os.getenv("AZURE_OPENAI_API_KEY")
	azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
	api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
	timeout_seconds = float(os.getenv("AZURE_OPENAI_TIMEOUT", "30"))

	if not api_key:
		raise ValueError("Missing AZURE_OPENAI_API_KEY in .env")
	if not azure_endpoint:
		raise ValueError("Missing AZURE_OPENAI_ENDPOINT in .env")

	return AzureOpenAI(
		api_version=api_version,
		azure_endpoint=azure_endpoint,
		api_key=api_key,
		timeout=timeout_seconds,
	)


def run_one_shot(client: AzureOpenAI, model_name: str, prompt: str) -> None:
	response = client.chat.completions.create(
		messages=[
			{"role": "system", "content": "You are a helpful assistant."},
			{"role": "user", "content": prompt},
		],
		max_tokens=512,
		temperature=1.0,
		top_p=1.0,
		model=model_name,
	)

	print(response.choices[0].message.content or "")


def run_chat(client: AzureOpenAI, model_name: str) -> None:
	print("Azure OpenAI chat is ready. Type 'exit' to quit.\n")

	messages = [
		{
			"role": "system",
			"content": "You are a helpful assistant.",
		}
	]

	while True:
		user_input = input("You: ").strip()
		if user_input.lower() in {"exit", "quit"}:
			print("Goodbye!")
			break
		if not user_input:
			continue

		messages.append({"role": "user", "content": user_input})

		response = client.chat.completions.create(
			model=model_name,
			messages=messages,
			temperature=0.7,
		)

		assistant_reply = response.choices[0].message.content or ""
		print(f"Assistant: {assistant_reply}\n")

		messages.append({"role": "assistant", "content": assistant_reply})


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Azure OpenAI chat script")
	parser.add_argument(
		"--prompt",
		help="Run one request and exit. If omitted, starts interactive chat.",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	client = build_client()
	model_name = os.getenv("AZURE_OPENAI_MODEL", "gpt-4o")

	if args.prompt:
		run_one_shot(client, model_name, args.prompt)
		return

	run_chat(client, model_name)


if __name__ == "__main__":
	main()
