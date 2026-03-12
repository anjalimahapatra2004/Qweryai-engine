from pydantic import BaseModel, Field

class TicketInput(BaseModel):
    title:       str = Field(default="", description="Title of the ticket")
    body:        str = Field(default="", description="Detailed description of the issue")
    subject:     str = Field(default="", description="Subject of the ticket")
    customer_id: str = Field(default="", description="ID of the customer")


class UserInput(BaseModel):
    firstname:   str = Field(default="", description="First name of the user")
    lastname:    str = Field(default="", description="Last name of the user")
    email:       str = Field(default="", description="Email of the user")
    title:       str = Field(default="", description="Title of the user's issue")
    subject:     str = Field(default="", description="Subject of the user's issue")
    description: str = Field(default="", description="Description of the user's issue")


class SearchUserInput(BaseModel):
    email: str = Field(default="", description="Email of the user to search for")