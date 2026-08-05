from llama_cloud import LlamaCloud
from dotenv import load_dotenv
import os
from pydantic import BaseModel,Field
from flask import Flask

load_dotenv()

client=LlamaCloud(api_key=os.getenv("LLAMA_CLOUD_API_KEY"))


file=client.files.create(file="./ProcureAgent_OS_Project_Report.pdf",purpose="parse")

result=client.parsing.parse(
        file_id=file.id,
        tier="agentic",
        version="latest",
        expand=["markdown"]
    )


parsed_pdf_list=result.markdown.pages


with open('parsings.txt','w') as f:
    for i in parsed_pdf_list:
        f.write(str(i))
