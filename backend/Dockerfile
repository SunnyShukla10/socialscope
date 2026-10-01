FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN addgroup --system --gid 10001 socialscope \
    && adduser --system --uid 10001 --ingroup socialscope --home /home/socialscope socialscope \
    && mkdir -p /tmp/socialscope_exports \
    && chown -R socialscope:socialscope /app /tmp/socialscope_exports

COPY --chown=socialscope:socialscope . .

ENV PYTHONDONTWRITEBYTECODE=1
USER socialscope

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
