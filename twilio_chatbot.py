from app import response_langchain
from twilio.rest import Client
from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from langchain_community.llms import CTransformers
from urllib.parse import parse_qs
import logging
from dotenv import dotenv_values
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from google.cloud import dialogflow_v2 as dialogflow


dialogflow_session_client= dialogflow.SessionsClient()
PROJECT_ID="gen-lang-client-0636853447"

config= dotenv_values('.env')
app= FastAPI()

TWILIO_ACCOUNT_SID=config["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN=config["TWILIO_AUTH_TOKEN"]
TWILIO_FROM_NUMBER=config["TWILIO_FROM_NUMBER"]
TWILIO_TO_NUMBER=config["TWILIO_TO_NUMBER"]

account_sid = TWILIO_ACCOUNT_SID
auth_token = TWILIO_AUTH_TOKEN
client = Client(account_sid, auth_token)
twilio_from_number = TWILIO_FROM_NUMBER 
twilio_to_number = TWILIO_TO_NUMBER 

# Set up logging
logging.basicConfig(filename="whatsapp_logfile.log",format='%(asctime)s %(message)s',filemode='w')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

llm = CTransformers(
    model="openhermes-2.5-mistral-7b.Q4_K_M.gguf", callbacks=[StreamingStdOutCallbackHandler()]
)


def send_message(to_number, body_text):
    try:
        message= client.messages.create(from_=f"whatsapp:{twilio_from_number}", body= body_text, to=f"whatsapp:{to_number}")
        logger.info(f"Message sent to {to_number}: {message.body}")
    except Exception as e:
        logger.error(f"Error sending message to {to_number}: {e}")


# @app.post("/")
# async def reply(question: Request):
#     llm_question= parse_qs(await question.body())[b'Body'][0].decode()
#     try:
#         chat_response = response_langchain(llm_question, llm)
#         send_message(twilio_to_number, chat_response)
#     except:
#          send_message(twilio_to_number, "wait")
#     return chat_response                                                                                                     


@app.post("/")
async def reply(question: Request):
    try:
        llm_question= parse_qs(await question.body())[b'Body'][0].decode()
        # Dialogflow response
        session= dialogflow_session_client.session_path(PROJECT_ID,twilio_to_number)
        text_input= dialogflow.TextInput(text= llm_question, language_code='en')
        query_input= dialogflow.QueryInput(text=text_input)

        response= dialogflow_session_client.detect_intent(request={"session":session, "query_input":query_input})
        chat_response= response.query_result.fulfillment_text
        logger.info(f"Dialogflow response:{chat_response} Confidence Level: {response.query_result.intent_detection_confidence}")

        if response.query_result.intent_detection_confidence<0.7:
            try:
                # llm response
                chat_response = response_langchain(llm_question, llm)
                send_message(twilio_to_number, chat_response)
                logger.info(f"LLM response:{chat_response}")
            except:
                send_message(twilio_to_number,'wait')
        else:
            send_message(twilio_to_number,chat_response)
        return JSONResponse(content={"reply":chat_response})
        
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)