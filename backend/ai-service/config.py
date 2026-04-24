import json
from typing import List, Dict, Any, Optional
from langchain_mcp_adapters.client import BaseTool


import yaml
def get_config():
    with open('configs/config.yml', encoding='utf-8') as cfgFile:
        config_app = yaml.safe_load(cfgFile)
        cfgFile.close()
    return config_app

def get_prompts():
    with open('configs/prompts.yml', encoding='utf-8') as promptFile:
        prompts = yaml.safe_load(promptFile)
        promptFile.close()
    return prompts

def format_tools_description(tools: List[BaseTool]) -> str:
    if not tools:
        return "No tools are currently available."

    tool_descriptions = []
    for tool in tools:
        try:
            tool_descriptions.append(
                f"""
Tool: {tool.name}
Description: {tool.description}
Parameters: {json.dumps(tool.args)}
"""
            )
        except Exception as e:
            print(f"Error formatting tool {tool.name}: {e}")
            tool_descriptions.append(
                f"""
Tool: {tool.name}
Description: {tool.description}
Parameters: Error formatting parameters
"""
            )

    return "\n".join(tool_descriptions)