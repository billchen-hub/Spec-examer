import os
import json
import logging
import requests
from typing import List, Dict

logger = logging.getLogger("[NexusClient]")

class NexusClient:
    def __init__(self, key: str):
        self.base_url = "http://ainexus.phison.com:5155"
        self.api_key = key
        if not self.api_key:
            logger.warning("NEXUS_API_KEY not found! LLM will fail.")

    async def generate_response(self, share_code: str, history: List[Dict], system_prompt: str = None, files: List[Dict] = []) -> str:
        """
        Assemble chat history and system prompt and call the llm endpoint
        """
        try:
            url = f"{self.base_url}/api/external/v1/callAgent/json"
            messages = [{"role": 0, "message": system_prompt}] if system_prompt else []
            
            for msg in history:
                messages.append({
                    "role": msg["role"], # user or assistant
                    "message": msg["content"]
                })

            # print(messages)
            # print(files)
            # print(messages[-1]['message'])
            # print(messages[:-1])
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': self.api_key
            }
            payload = {
                'shareCode': share_code,
                'prompt': "<<<" + messages[-1]['message'] + ">>>",
                'previousMessage': messages[:-1],
                'files': files
            }
            # print(payload)

            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status() 

            response_data = response.json()
            json_string = json.dumps(response_data, indent=4, ensure_ascii=False)
            logger.info(f"API Response JSON:\n{json_string}")

            return response_data['content']
        except requests.exceptions.Timeout:
            return "抱歉，Robot 詢問 AI Nexus Timeout，可能在維修，請稍後再試。"
        except requests.exceptions.RequestException as e:
            # Handle any errors during the request
            logger.error(f"Post request error: {e}")
            if hasattr(response, 'status_code'):
                logger.error(f"Status Code: {response.status_code}")
                logger.error(f"Response Body: {response.text}")
            return "抱歉，Robot 詢問 AI Nexus 時出錯了，請稍後再試。"
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            return "抱歉，Robot 詢問 AI Nexus 時出錯了，請稍後再試。"

    async def upload_file(self, path: str) -> int:
        try:
            url = f"{self.base_url}/api/external/v1/Files/upload"
            with open(path, 'rb') as file:
                files = { "file": file }
                headers = { 'X-API-Key': self.api_key }
                form_data = {
                    'description': 'test', 
                    'isPublic': False
                }
                response = requests.post(url, data=form_data, files=files, headers=headers, timeout=120)
                response.raise_for_status() 

                response_data = response.json()
                # print("Response Data:", response_data)

                return response_data['data']['fileId']
        except requests.exceptions.Timeout:
            return "抱歉，Robot 詢問 AI Nexus Timeout，可能在維修，請稍後再試。"
        except Exception as e:
            logger.error(f"LLM upload images error: {e}")
            return None