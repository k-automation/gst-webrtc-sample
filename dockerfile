FROM ubuntu:20.10

WORKDIR /opt/gst-app
COPY . .

RUN DEBIAN_FRONTEND="noninteractive" apt-get update && apt-get -y install tzdata

RUN apt-get update && apt-get install -y \
    libgstreamer1.0-0 gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly gstreamer1.0-libav \
    gstreamer1.0-doc gstreamer1.0-tools \
    gir1.2-gst-plugins-bad-1.0

RUN apt-get update && apt-get install -y \
    gstreamer1.0-nice 

RUN apt-get update && apt-get install -y \
    python3 python3-pip

RUN apt-get update && apt-get install -y \
    libcairo2 libcairo2-dev libgirepository1.0-dev

RUN pip3 install --no-cache-dir -r requirements.txt

EXPOSE 8080

CMD ["python3", "./server.py"]