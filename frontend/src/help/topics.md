# Topics

Topics groups your emails into subjects automatically, so you can browse by theme instead of by sender. Running it also prepares the "meaning" index that Smart search, Similar emails and Case semantic search rely on.

## Controls

- **Run Clustering** reads every email, builds embeddings and groups them. On a large archive this takes a long time (tens of minutes for tens of thousands of emails). You can leave the page and come back, and progress continues.
- A **Cancel** button appears while it runs. Embeddings already made are kept.
- The **Ollama: Connected / Offline** badge shows whether the model server is reachable. If offline, start it first.
- The model name button (for example `nomic-embed-text`) lists installed and suggested embedding models. The model is chosen with `EMBED_MODEL` in `.env`, and changing it needs a restart and a new clustering run.
- Each topic shows a label, keywords and the number of emails. Click one to see ten of its emails.

![Topics list with keywords and email counts](/help/topics.png)

## Example

Run clustering once after your first import. Afterwards, open **Emails** and switch the search to **Smart**: it now understands meaning.

> **Careful:** Without embeddings, Smart search, **Similar** and the semantic part of Case searches have nothing to work with. A Case run will report "no embeddings indexed" for that channel.
