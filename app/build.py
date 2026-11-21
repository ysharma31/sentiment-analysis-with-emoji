"""Build app/index.html from the template, embedding the system prompt from prompts/."""
import json, pathlib, re
root = pathlib.Path(__file__).resolve().parent.parent
md = (root / "prompts/sentiment_analysis_prompt.md").read_text()
prompt = re.search(r"## System Prompt\s*```\n(.*?)\n```", md, re.S).group(1)
tpl = (root / "app/index.template.html").read_text()
(root / "app/index.html").write_text(tpl.replace("__SYSTEM_PROMPT__", json.dumps(prompt, ensure_ascii=False)))
print("built app/index.html, prompt chars:", len(prompt))
