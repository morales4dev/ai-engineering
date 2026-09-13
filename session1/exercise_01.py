import os
from dotenv import load_dotenv
import litellm
from openai import OpenAI
from rich import print

load_dotenv(override=True)

openai_api_key = os.getenv('OPENAI_API_KEY')
if openai_api_key:
    print(f"OpenAI API Key exists and begins {openai_api_key[:8]}")
else:
    print("OpenAI API Key not set - please head to the troubleshooting guide in the setup folder")

anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
if anthropic_api_key:
    print(f"Anthropic API Key exists and begins {anthropic_api_key[:8]}")
else:
    print("Anthropic API Key not set - please head to the troubleshooting guide in the setup folder")

messages = [{"role": "system", "content": "You are a mix between a funny writer with comedic skills and a comedian with writing skills. You cant speak english. Your mother language is spanish."},
            {"role": "user", "content": "Tell me a fun fact disregarding sea animals"}]

## Anthropic
model_name = "anthropic/claude-haiku-4-5"
response = litellm.completion(
    model=model_name,
    api_key=anthropic_api_key, 
    messages=messages,
    temperature=0.7,
    max_tokens=1000
)
print(f"[bold yellow]Anthropic:[/bold yellow] {response.choices[0].message.content}\n\n")

## OpenAI
client = OpenAI()
model_name="gpt-5.6-luna"
response = client.chat.completions.create(
    model=model_name,
    messages=messages
)

print(f"[bold yellow]OpenAI:[/bold yellow] {response.choices[0].message.content}")