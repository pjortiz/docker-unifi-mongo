# docker-unifi-mongo <!-- omit in toc -->

## Table of Contents <!-- omit in toc -->

- [Quick reference](#quick-reference)
- [About](#about)
- [Usage](#usage)
	- [Docker Compose](#docker-compose)
	- [Docker CLI](#docker-cli)
		- [Create the network](#create-the-network)
		- [Create the volume](#create-the-volume)
		- [Run the MongoDB container](#run-the-mongodb-container)
- [Build Your Own Image](#build-your-own-image)

_______________________________________

## Quick reference
- [pjortiz/docker-compose-unifi-network-application](https://github.com/pjortiz/docker-compose-unifi-network-application)
- [Mongo](https://hub.docker.com/_/mongo) Official Image
- [linuxserver/unifi-network-application](https://hub.docker.com/r/linuxserver/unifi-network-application) Official Image

_______________________________________

## About

This image is packaged with the require mongo init script to set up [linuxserver/unifi-network-application](https://hub.docker.com/r/linuxserver/unifi-network-application).

_______________________________________

## Usage

### Docker Compose

```yaml
version: "3.7"
networks:
  # proxy-network: # optional, Use this network or your own if you intend to configure the unifi-network-application container through a revers proxy, otherwise not needed.
    # external: true
  unifi:
volumes: # You can change the volumes' device path if you want, otherwise no need to change, default Docker volume folder location will be used 
  unifi_mongo_data:
services:
  unifi-mongo-db:
    image: portiz93/unifi-mongo:${MONGO_VERSION:-6.0.15}    # Required MONGO_VERSION, Default "6.0.15", specify whatever Mongo version tag you need. DO NOT set 'latest' tag
    container_name: unifi-mongo-db
    environment:
      - MONGO_USER=${MONGO_USER:-unifi}                     # Default "unifi"
      - MONGO_PASS=${MONGO_PASS:?Mongo Password Required}   # Required
      - MONGO_DBNAME=${MONGO_DBNAME:-unifi}                 # Default "unifi"
    volumes:
      - unifi_mongo_data:/data/db
    # ports:
    #   - 27017:27017                                       # optional, Default "27017", only port if needed outside of unifi app
    networks:
      unifi:
    restart: unless-stopped
```

### Docker CLI

#### Create the network

```bash
docker network create unifi
```

#### Create the volume

```bash
docker volume create unifi_mongo_data
```

#### Run the MongoDB container

```bash
docker run -d \
  --name unifi-mongo-db \
  --network unifi \
  -v unifi_mongo_data:/data/db \
  -e MONGO_USER=unifi \
  -e MONGO_PASS=your_mongo_password_here \
  -e MONGO_DBNAME=unifi \
  --restart unless-stopped \
  portiz93/unifi-mongo:6.0.15
```

_______________________________________

## Build Your Own Image

```bash
docker build -t unifi-mongo:6.0.15 --build-arg MONGO_VERSION=6.0.15 . 
```
