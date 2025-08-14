import os
import time
import openai
from dotenv import load_dotenv

# Загружаем .env из текущей директории
load_dotenv()

# Проверяем, что переменная окружения реально подхватилась
print("OPENAI_API_KEY =", os.getenv("OPENAI_API_KEY"))

# Установи ключ API в переменной окружения
openai.api_key = os.getenv("OPENAI_API_KEY")

# 1. Создаём ассистента (один раз)
def create_assistant():
    assistant = openai.beta.assistants.create(
        name="Test Assistant",
        instructions="Ты — тестовый ассистент, который отвечает дружелюбно и коротко.",
        model="gpt-4o-mini"
    )
    print("Assistant ID:", assistant.id)
    return assistant.id

# 2. Создаём поток (thread) для истории чата
def create_thread():
    thread = openai.beta.threads.create()
    print("Thread ID:", thread.id)
    return thread.id

# 3. Отправляем сообщение пользователем
def send_message(thread_id, content):
    openai.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=content
    )

# 4. Запускаем ответ ассистента
def run_assistant(thread_id, assistant_id):
    run = openai.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id
    )
    return run.id

# 5. Ждём пока GPT ответит
def wait_for_completion(thread_id, run_id):
    while True:
        run = openai.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        if run.status == "completed":
            break
        time.sleep(1)

# 6. Получаем последнее сообщение
def get_last_message(thread_id):
    messages = openai.beta.threads.messages.list(thread_id=thread_id)
    return messages.data[-1].content[0].text.value

if __name__ == "__main__":
    assistant_id = create_assistant()
    thread_id = create_thread()

    # Пример общения
    send_message(thread_id, "Привет! Как дела?")
    run_id = run_assistant(thread_id, assistant_id)
    wait_for_completion(thread_id, run_id)
    print("GPT:", get_last_message(thread_id))

    send_message(thread_id, "Расскажи короткий анекдот.")
    run_id = run_assistant(thread_id, assistant_id)
    wait_for_completion(thread_id, run_id)
    print("GPT:", get_last_message(thread_id))
