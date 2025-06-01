import json
import boto3
import uuid
from datetime import datetime

# Create DynamoDB client
dynamodb = boto3.client('dynamodb')

def lambda_handler(event, context):
    # Log the user input
    print(f"The user input is {event}")

    # Extract parameters from event['parameters'] or event['requestBody']['content']['application/json']['properties']
    parameters = {}
    if 'parameters' in event and event['parameters']:
        parameters = {param['name']: param['value'] for param in event['parameters']}
    elif 'requestBody' in event and 'content' in event['requestBody'] and 'application/json' in event['requestBody']['content']:
        if 'properties' in event['requestBody']['content']['application/json']:
            parameters = {prop['name']: prop['value'] for prop in event['requestBody']['content']['application/json']['properties']}
        elif 'body' in event['requestBody']['content']['application/json']:
            body = json.loads(event['requestBody']['content']['application/json']['body'])
            parameters = {
                'roomType': body.get('roomType'),
                'date': body.get('date'),
                'customerName': body.get('customerName')
            }

    # Extract required parameters
    room_type = parameters.get('roomType')
    date = parameters.get('date')
    customer_name = parameters.get('customerName')

    # Validate input parameters
    if not all([room_type, date, customer_name]):
        error_response = {
            'error': 'Missing required parameters: roomType, date, or customerName'
        }
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup', 'HotelRoomBooking'),
                'apiPath': event.get('apiPath', '/bookings'),
                'httpMethod': event.get('httpMethod', 'POST'),
                'httpStatusCode': 400,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps(error_response)
                    }
                },
                'sessionAttributes': event.get('sessionAttributes', {}),
                'promptSessionAttributes': event.get('promptSessionAttributes', {})
            }
        }

    # Validate room_type
    valid_room_types = ['Single', 'Double', 'Suite']
    if room_type not in valid_room_types:
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup', 'HotelRoomBooking'),
                'apiPath': event.get('apiPath', '/bookings'),
                'httpMethod': event.get('httpMethod', 'POST'),
                'httpStatusCode': 400,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps({'error': f'Invalid roomType: {room_type}. Must be one of {valid_room_types}'})
                    }
                },
                'sessionAttributes': event.get('sessionAttributes', {}),
                'promptSessionAttributes': event.get('promptSessionAttributes', {})
            }
        }

    # Check room availability in RoomAvailability table
    try:
        response = dynamodb.get_item(
            TableName='RoomAvailability',
            Key={
                'RoomType': {'S': room_type},
                'Date': {'S': date}
            }
        )
        item = response.get('Item', {})
        available_rooms = int(item.get('AvailableRooms', {'N': '0'})['N'])
    except Exception as e:
        print(f"Error querying RoomAvailability: {str(e)}")
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup', 'HotelRoomBooking'),
                'apiPath': event.get('apiPath', '/bookings'),
                'httpMethod': event.get('httpMethod', 'POST'),
                'httpStatusCode': 500,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps({'error': 'Failed to check room availability'})
                    }
                },
                'sessionAttributes': event.get('sessionAttributes', {}),
                'promptSessionAttributes': event.get('promptSessionAttributes', {})
            }
        }

    # Verify if room is available
    if available_rooms <= 0:
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup', 'HotelRoomBooking'),
                'apiPath': event.get('apiPath', '/bookings'),
                'httpMethod': event.get('httpMethod', 'POST'),
                'httpStatusCode': 400,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps({'error': f'No available rooms for {room_type} on {date}'})
                    }
                },
                'sessionAttributes': event.get('sessionAttributes', {}),
                'promptSessionAttributes': event.get('promptSessionAttributes', {})
            }
        }

    # Generate unique BookingId
    booking_id = str(uuid.uuid4())

    # Create booking in Bookings table
    try:
        dynamodb.put_item(
            TableName='Bookings',
            Item={
                'BookingId': {'S': booking_id},
                'Date': {'S': date},
                'CustomerName': {'S': customer_name},
                'RoomType': {'S': room_type},
                'Status': {'S': 'Confirmed'}
            }
        )
    except Exception as e:
        print(f"Error creating booking: {str(e)}")
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup', 'HotelRoomBooking'),
                'apiPath': event.get('apiPath', '/bookings'),
                'httpMethod': event.get('httpMethod', 'POST'),
                'httpStatusCode': 500,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps({'error': 'Failed to create booking'})
                    }
                },
                'sessionAttributes': event.get('sessionAttributes', {}),
                'promptSessionAttributes': event.get('promptSessionAttributes', {})
            }
        }

    # Update RoomAvailability by decrementing AvailableRooms
    try:
        dynamodb.update_item(
            TableName='RoomAvailability',
            Key={
                'RoomType': {'S': room_type},
                'Date': {'S': date}
            },
            UpdateExpression='SET AvailableRooms = AvailableRooms - :val',
            ExpressionAttributeValues={
                ':val': {'N': '1'}
            }
        )
    except Exception as e:
        print(f"Error updating RoomAvailability: {str(e)}")
        # Optionally, rollback the booking if update fails
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup', 'HotelRoomBooking'),
                'apiPath': event.get('apiPath', '/bookings'),
                'httpMethod': event.get('httpMethod', 'POST'),
                'httpStatusCode': 500,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps({'error': 'Failed to update room availability'})
                    }
                },
                'sessionAttributes': event.get('sessionAttributes', {}),
                'promptSessionAttributes': event.get('promptSessionAttributes', {})
            }
        }

    # Format success response
    response_body = {
        'bookingId': booking_id,
        'roomType': room_type,
        'date': date,
        'customerName': customer_name,
        'status': 'Confirmed'
    }

    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': event.get('actionGroup', 'HotelRoomBooking'),
            'apiPath': event.get('apiPath', '/bookings'),
            'httpMethod': event.get('httpMethod', 'POST'),
            'httpStatusCode': 200,
            'responseBody': {
                'application/json': {
                    'body': json.dumps(response_body)
                }
            },
            'sessionAttributes': event.get('sessionAttributes', {}),
            'promptSessionAttributes': event.get('promptSessionAttributes', {})
        }
    }
