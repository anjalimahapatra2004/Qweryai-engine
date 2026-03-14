# from pydantic import BaseModel

# class ChatMessage(BaseModel):
#     role:    str
#     content: str


# class MessagesRequest(BaseModel):
#     message:      str
#     chat_history: list[ChatMessage] = []
#     customer_id:  str
#     firstname:    str
#     lastname:     str


from pydantic import BaseModel


class ChatMessage(BaseModel):
    role:    str
    content: str


class MessagesRequest(BaseModel):
    message:      str
    chat_history: list[ChatMessage] = []
    customer_id:  str
    firstname:    str
    lastname:     str


    # Zoho credentials 
    access_token: str = ""   
    zoho_email:   str = ""   