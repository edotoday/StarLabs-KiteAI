
import random
import asyncio
import json
from loguru import logger

from src.model.kiteai.constants import KiteAIProtocol, Agents
from src.utils.decorators import retry_async
from src.utils.constants import EXPLORER_URL_KITEAI


class OzoneAIChat:
    def __init__(self, kiteai_instance: KiteAIProtocol):
        self.kiteai = kiteai_instance

    async def _extract_response_content(self, response_data):
        """Extract content from AI response"""
        # Handle different response formats
        response_text = ""
        if hasattr(response_data, "text") and isinstance(response_data.text, str):
            response_text = response_data.text
        elif hasattr(response_data, "content"):
            response_text = response_data.content.decode("utf-8", "ignore")
        elif isinstance(response_data, (bytes, bytearray)):
            response_text = response_data.decode("utf-8", "ignore")
        else:
            response_text = str(response_data)

        content_parts = []
        for line in response_text.splitlines():
            cleaned_line = line.strip()
            if not cleaned_line.startswith("data:") or cleaned_line == "data: [DONE]":
                continue
                
            try:
                json_content = json.loads(cleaned_line[5:].strip())
                choices = json_content.get("choices", [{}])
                if choices:
                    delta_content = choices[0].get("delta", {}).get("content")
                    if delta_content:
                        content_parts.append(delta_content)
            except json.JSONDecodeError:
                pass

        return "".join(content_parts).strip()

    async def _process_streaming_response(self, response_data):
        """Process streaming response from AI"""
        accumulated_content = ""
        
        for content_line in response_data.content:
            decoded_line = content_line.decode("utf-8").strip()
            
            if not decoded_line.startswith("data:"):
                continue
            if decoded_line == "data: [DONE]":
                break
                
            try:
                parsed_data = json.loads(decoded_line[5:].strip())
                choice_delta = parsed_data.get("choices", [{}])[0].get("delta", {})
                text_content = choice_delta.get("content")
                if text_content:
                    accumulated_content += text_content
            except json.JSONDecodeError:
                continue

        return accumulated_content.strip()

    @retry_async(default_value=None)
    async def _send_conversation_receipt(self, service_id, user_query, ai_answer):
        """Submit conversation receipt to the server"""
        try:
            request_data = {
            "address": self.kiteai.eoa_address,
            "input": [{"type": "text/plain", "value": user_query}],
            "output": [{"type": "text/plain", "value": ai_answer}],
            "service_id": service_id,
        }

            request_headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'authorization': f'Bearer {self.kiteai.kiteai_login_token}',
                'content-type': 'application/json',
                'origin': 'https://testnet.gokite.ai',
                'priority': 'u=1, i',
                'referer': 'https://testnet.gokite.ai/',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            }

            api_response = await self.kiteai.session.post(
                "https://neo.prod.gokite.ai/v2/submit_receipt", 
                headers=request_headers, 
                json=request_data
            )
            
            if not (200 <= api_response.status_code < 300):
                raise Exception(f"Receipt submission failed: {api_response.status_code} | {api_response.text}")

            return api_response.json().get('data')

        except Exception as error:
            wait_time = random.randint(
                self.kiteai.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.kiteai.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.kiteai.account_index} | Receipt submission error: {error}. Waiting {wait_time} seconds..."
            )
            await asyncio.sleep(wait_time)
            raise

    @retry_async(attempts=5, default_value=None)
    async def _fetch_inference_result(self, conversation_id):
        """Retrieve inference result by conversation ID"""
        try:
            auth_headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'authorization': f'Bearer {self.kiteai.kiteai_login_token}',
                'origin': 'https://testnet.gokite.ai',
                'priority': 'u=1, i',
                'referer': 'https://testnet.gokite.ai/',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            }

            api_response = await self.kiteai.session.get(
                f"https://neo.prod.gokite.ai/v1/inference?id={conversation_id}", 
                headers=auth_headers
            )
            
            if not (200 <= api_response.status_code < 300):
                raise Exception(f"Inference retrieval failed: {api_response.status_code} | {api_response.text}")

            transaction_hash = api_response.json().get("data", {}).get("tx_hash", "")

            if not transaction_hash:
                raise Exception(f'Transaction hash not found in response')

            return transaction_hash

        except Exception as error:
            if "Transaction hash not found in response" in str(error):
                logger.warning(f"{self.kiteai.account_index} | Transaction hash not found in response, waiting 5 seconds...")
                await asyncio.sleep(5)
                raise
            
            delay_seconds = random.randint(
                self.kiteai.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.kiteai.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.kiteai.account_index} | Inference fetch error: {error}. Pausing {delay_seconds} seconds..."
            )
            await asyncio.sleep(delay_seconds)
            raise

    @retry_async(default_value=None)
    async def _interact_with_ai_agent(self, service_id, user_prompt):
        """Send request to AI agent and get response"""
        try:
            request_payload = {
            "service_id": service_id,
            "body": {"message": user_prompt, "stream": True},
            "stream": True,
            "subnet": "kite_ai_labs",
        }

            stream_headers = {
                'accept': 'text/event-stream',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'authorization': f'Bearer {self.kiteai.kiteai_login_token}',
                'content-type': 'application/json',
                'origin': 'https://testnet.gokite.ai',
                'priority': 'u=1, i',
                'referer': 'https://testnet.gokite.ai/',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            }

            ai_response = await self.kiteai.session.post(
                "https://ozone-point-system.prod.gokite.ai/agent/inference", 
                headers=stream_headers, 
                json=request_payload
            )

            if ai_response.status_code <= 202:
                parsed_answer = await self._extract_response_content(response_data=ai_response)
                return parsed_answer

            if ai_response.status_code == 429:
                logger.warning(f"{self.kiteai.account_index} | AI conversation rate limit exceeded")
                return None

            raise Exception(f"AI agent interaction failed: {ai_response.status_code} | {ai_response.text}")

        except Exception as error:
            sleep_duration = random.randint(
                self.kiteai.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.kiteai.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.kiteai.account_index} | AI agent interaction error: {error}. Waiting {sleep_duration} seconds..."
            )
            await asyncio.sleep(sleep_duration)
            raise

    async def ozone_ai_chat(self):
        """Main method to handle AI agent conversations"""
        try:
            logger.info(f"{self.kiteai.account_index} | Initializing Ozone AI conversation...")
            
            await asyncio.sleep(1)
            agent_collection = Agents()

            selected_agent = random.choice(agent_collection.agents)

            agent_service = selected_agent["service"]
            agent_identifier = selected_agent["agent"]
            available_questions = selected_agent["questions"]

            chosen_question = random.choice(available_questions)

            # Enhanced question for Sherlock agent with transaction hash
            if agent_identifier == 'Sherlock':
                generated_tx_hash = '0x' + ''.join(random.choices('0123456789abcdef', k=64))
                chosen_question = f"{chosen_question} {generated_tx_hash}"

            logger.info(f"{self.kiteai.account_index} | Agent: {agent_identifier} | Query: {chosen_question}")

            # Obtain AI agent response
            agent_response = await self._interact_with_ai_agent(service_id=agent_service, user_prompt=chosen_question)
            
            if agent_response is None:
                logger.warning(f"{self.kiteai.account_index} | Rate limit exceeded, stopping conversation")
                return False
                
            logger.info(f"{self.kiteai.account_index} | Agent: {agent_identifier} | Response: {agent_response}")

            # Process conversation receipt
            receipt_data = await self._send_conversation_receipt(
                service_id=agent_service, 
                user_query=chosen_question, 
                ai_answer=agent_response
            )

            if not receipt_data.get('id'):
                raise Exception("Conversation identifier missing from receipt response")

            await asyncio.sleep(random.randint(3, 5))

            # Retrieve final transaction result
            transaction_result = await self._fetch_inference_result(conversation_id=receipt_data['id'])

            if transaction_result:
                logger.success(
                    f"{self.kiteai.account_index} | Agent: {agent_identifier} | "
                    f"Conversation finalized | TX: {EXPLORER_URL_KITEAI}{transaction_result}"
                )
                return True

            return False

        except Exception as error:
            retry_delay = random.randint(
                self.kiteai.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.kiteai.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.kiteai.account_index} | Ozone AI conversation error: {error}. "
                f"Retrying in {retry_delay} seconds..."
            )
            await asyncio.sleep(retry_delay)
            return False