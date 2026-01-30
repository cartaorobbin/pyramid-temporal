FROM mcr.microsoft.com/devcontainers/base:jammy

RUN sudo apt update \
    && sudo apt install -y \
    iputils-ping \
    bash-completion \
    direnv \
    postgresql \
    postgresql-contrib \
    && rm -rf /var/lib/apt/lists/*

ARG USERNAME=vscode

RUN SNIPPET="export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
    && mkdir /commandhistory \
    && touch /commandhistory/.bash_history \
    && chown -R $USERNAME /commandhistory \
    && echo "$SNIPPET" >> "/home/$USERNAME/.bashrc"

RUN echo '# Configuring bash_completion' >> "/home/$USERNAME/.bashrc"
RUN echo "source /etc/profile.d/bash_completion.sh" >> "/home/$USERNAME/.bashrc"

RUN echo '# Configuring direnv' >> "/home/$USERNAME/.bashrc"
RUN echo 'eval "$(direnv hook bash)"' >> "/home/$USERNAME/.bashrc"

RUN echo '# Configuring poetry' >> "/home/$USERNAME/.bashrc"
RUN echo 'poetry shell || true' >> "/home/$USERNAME/.bashrc"
