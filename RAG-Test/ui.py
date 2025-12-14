import gradio as gr
from query import answer_question




def chat_fn(user_msg, history):
    history = history or []

    out = answer_question(user_msg)
    answer = out["answer"]
    sources = out.get("sources", [])

    src_text = ""
    if sources:
        flat = sources[0] if isinstance(sources[0], list) else sources
        lines = []
        for meta in flat:
            title = meta.get("title", "")
            url = meta.get("url", "")
            lines.append(f"{title} — {url}")
        src_text = "\n".join(lines)

    full_answer = answer
    if src_text:
        full_answer += "\n\nИсточники:\n" + src_text

    history.append({
        "role": "user",
        "content": user_msg
    })
    history.append({
        "role": "assistant",
        "content": full_answer
    })

    return history, history




with gr.Blocks() as demo:
    gr.Markdown("# RAG Tutor — Demo")
    chatbot = gr.Chatbot()
    msg = gr.Textbox(placeholder="Задайте вопрос по материалам...")
    state = gr.State([])

    msg.submit(chat_fn, inputs=[msg, state], outputs=[chatbot, state])



if __name__ == '__main__':
    demo.launch()