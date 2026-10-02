"""Debug one factual question. Prints no secrets."""

from src.config import Settings
from src.query.guards import manifest_urls
from src.query.llm import GroqClient
from src.query.prompt import assemble_context, build_messages
from src.query.retrieve import retrieve
from src.query.validate import _issues

question = "What is the exit load of SBI Flexicap Fund?"
settings = Settings.from_env()
result = retrieve(question, settings)
print("ooc", result.out_of_corpus, "max", round(result.max_similarity, 3), "hits", len(result.hits))
for hit in result.hits:
    print(" score", round(hit.score, 3), "scheme", hit.metadata.get("scheme"), "url_tail", str(hit.metadata.get("source_url", ""))[-40:])
    print("  has_exit", "exit load" in hit.text.lower())
context = assemble_context(result.hits)
client = GroqClient(settings)
response = client._client.chat.completions.create(
    model=settings.llm_model,
    messages=build_messages(context, question),
    temperature=0,
    max_tokens=settings.llm_max_tokens,
)
message = response.choices[0].message
content = message.content or ""
reasoning = getattr(message, "reasoning", None) or ""
print("content_len", len(content))
print("reasoning_len", len(str(reasoning)))
print("issues", sorted(_issues(content, result.hits, manifest_urls())))
from pathlib import Path

Path("_debug_out.txt").write_text(
    "content=" + repr(content) + "\nreasoning_has_url=" + str("http" in str(reasoning).lower()) + "\nreasoning_has_exit=" + str("exit" in str(reasoning).lower()) + "\n",
    encoding="utf-8",
)
print("wrote")
