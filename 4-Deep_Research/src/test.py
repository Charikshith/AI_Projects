import instructor
from pydantic import BaseModel
# from openai import OpenAI
from langfuse.openai import OpenAI

from langfuse import Langfuse

langfuse = Langfuse(
  secret_key="sk-lf-1796eac9-4a9b-4419-a011-",
  public_key="pk-lf-b4155098-9dc6-42b8-8044-",
  host="https://us.cloud.langfuse.com"
)

class Person(BaseModel):
    name: str
    age: int
    occupation: str

client = OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/", api_key="AIzaSyB1TdgFN")



# ===== CONFIGURATION =====
instructor_client = instructor.from_openai(client=client)

# logfire.instrument_openai(instructor_client)
# person ,completion = instructor_client.chat.completions.create_with_completion(
#     model="gemini-2.5-flash",
#     response_model=Person,
#     messages=[
#         {"role": "user", "content": " Vijay 56  as venture fund"}
#     ],
# )
# print(person)  # Person(name='John', age=30, occupation='software engineer')
# print('\n',completion.choices)
# # 3. Parse the raw JSON into our Pydantic model
# raw = completion.choices[0].message.content
# # remove ```json … ``` if present
# cleaned = raw.strip().removeprefix("```json").removesuffix("```")
# result = Person.model_validate_json(raw)

# print(result)

# result = client.chat.completions.create(
#     model="gemini-2.5-flash",
#     # response_model=str,
#     messages=[
#         {"role": "user", "content": " Vijay 56  as venture fund"}
#     ],
# )

# raw = result.choices[0].message.content
# # remove ```json … ``` if present
# cleaned = raw.strip().removeprefix("```json").removesuffix("```")
# results = Person.model_validate_json(raw)

# print(result)

from instructor import Partial

# Stream the response as it's being generated
stream = instructor_client.chat.completions.create_partial(
    model="gemini-2.5-flash",
    response_model=Person,
    messages=[
        {"role": "user", "content": "Extract a detailed person profile for John Steve, 35, who lives in Chicago and Springfield."}
    ],
)

for partial in stream:
    # This will incrementally show the response being built
    print(partial)