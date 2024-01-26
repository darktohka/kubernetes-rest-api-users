from flask import request
from .kafka import create_consumer, create_producer, register_kafka_listener
from kafka.structs import TopicPartition
import binascii
import os
import jwt

JWT_ROTATED_TOPIC = 'jwt-rotated'

jwt_secret = None

def get_jwt_secret():
    return jwt_secret

def set_jwt_secret(secret):
    print('Set JWT secret:', secret)

    global jwt_secret
    jwt_secret = secret

def create_jwt(user):
    identity = {'id': user['id'], 'username': user['username'], 'email': user['email'], 'roles': user['roles']}
    access_token = jwt.encode(identity, get_jwt_secret(), algorithm='HS256')
    return access_token

def get_jwt_identity():
    headers = request.headers
    bearer = headers.get('Authorization')
    token = bearer.split()[1]
    return jwt.decode(token, get_jwt_secret(), algorithms=['HS256'])

def rotate_jwt():
    print('Rotating JWT...')
    secret = binascii.hexlify(os.urandom(16)).decode('utf-8')
    set_jwt_secret(secret)

    producer.send(JWT_ROTATED_TOPIC, {'jwt': secret})
    producer.flush()

def rotate_jwt_if_necessary():
    consumer = create_consumer(JWT_ROTATED_TOPIC, auto_offset_reset='earliest')
    partition_number = next(iter(consumer.partitions_for_topic(JWT_ROTATED_TOPIC)))
    partition = TopicPartition(JWT_ROTATED_TOPIC, partition_number)

    consumer.seek_to_end(partition)
    end_position = consumer.position(partition)

    consumer.seek_to_beginning(partition)
    start_position = consumer.position(partition)

    if start_position == end_position:
        rotate_jwt()
        return

    print('JWT rotation not required.')

    # Read the latest message and set the JWT secret to the value in the message.
    consumer.seek(partition, end_position - 1)
    message = consumer.poll(timeout_ms=6000)
    on_jwt_rotated(message[partition][0])

def on_jwt_rotated(message):
    data = message.value
    secret = data['jwt']
    set_jwt_secret(secret)

producer = create_producer()

rotate_jwt_if_necessary()
register_kafka_listener(JWT_ROTATED_TOPIC, enable_auto_commit=False, auto_offset_reset='latest', listener=on_jwt_rotated)
