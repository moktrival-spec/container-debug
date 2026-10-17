ARG BASE_IMAGE=python:3.12-slim-bookworm
FROM ${BASE_IMAGE}
USER root
ENTRYPOINT []
WORKDIR /lab
COPY service.py bad.sh good.sh orphan.py proc_tree.py /lab/
STOPSIGNAL SIGTERM
CMD ["sh", "/lab/bad.sh"]
