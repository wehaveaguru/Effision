from llama_cloud import LlamaCloud
from dotenv import load_dotenv
import os
load_dotenv()

client=LlamaCloud()
client.api_key=os.getenv("LLAMA_CLOUD_API_KEY")


file=client.files.create(file="./ProcureAgent_OS_Project_Report.pdf",purpose="parse")

result=client.parsing.parse(
        file_id=file.id,
        tier="agentic",
        version="latest",
        expand=["markdown"]
    )

print(result.markdown.pages[0].markdown)
