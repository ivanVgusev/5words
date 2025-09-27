# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app


# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the .env file into the container
COPY .env /app/.env

# Expose the port the bot will run on (optional, for debugging purposes)
EXPOSE 8080

# Run the bot when the container launches
CMD ["python", "bot.py"]

# строка для сборки образа
# docker build -t 5words:latest .

