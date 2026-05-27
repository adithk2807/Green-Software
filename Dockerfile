# Base image: Ubuntu 22.04 (full Linux environment)
FROM ubuntu:22.04

# Prevent interactive prompts during apt install
ENV DEBIAN_FRONTEND=noninteractive

# Install nginx, Python, pip, and basic tools
RUN apt-get update && apt-get install -y \
    nginx \
    python3 \
    python3-pip \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages needed for the experiment
RUN pip3 install codecarbon locust

# Copy your entire project into the container at /app
COPY . /app

# Set working directory to /app
WORKDIR /app

# Create the results folder inside the container
RUN mkdir -p /app/results

# Expose port 80 so nginx can receive requests
EXPOSE 80

# Default command: open a bash shell
CMD ["/bin/bash"]