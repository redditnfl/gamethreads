FROM python:3.10-alpine3.16

WORKDIR /app

# thanks Norrius https://stackoverflow.com/a/47871121
RUN \
 apk add --no-cache postgresql-libs && \
 apk add --no-cache --virtual .build-deps gcc g++ musl-dev postgresql-dev git

COPY . /app/
RUN pip install -e . && \
 apk --purge del .build-deps

ENV \
  TZ="UTC" \
  PGUSER="postgres" \
  POSTGRES_PASSWORD="" \
  PGHOST="postgres" \
  PGPORT="5432" \
  PGDATABASE="postgres" \
  praw_user_agent="gamethreads/1.0" \
  praw_client_id="" \
  praw_client_secret="" \
  praw_refresh_token=""

ENTRYPOINT ["gamethreads"]
