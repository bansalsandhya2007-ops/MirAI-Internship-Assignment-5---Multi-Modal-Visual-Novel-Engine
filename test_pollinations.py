import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("POLLINATIONS_API_KEY")

print("API key loaded:", bool(api_key))

url = "https://gen.pollinations.ai/image/a%20fantasy%20castle%20at%20sunset?model=flux"

response = requests.get(
    url,
    headers={
        "Authorization": f"Bearer {api_key}"
    },
    timeout=60
)

print("Status code:", response.status_code)
print("Content type:", response.headers.get("content-type"))

if response.status_code == 200:
    with open("test_image.png", "wb") as f:
        f.write(response.content)

    print("SUCCESS: Image saved as test_image.png")
else:
    print("ERROR:")
    print(response.text) 