import json
import boto3
from datetime import datetime

# Create DynamoDB clients
dynamodb_client = boto3.client('dynamodb')
dynamodb_resource = boto3.resource('dynamodb')

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
            parameters = {'bookingId': body.get('bookingId')}

    # Extract required parameter
    booking_id = parameters.get('bookingId')

    # Validate input parameter
    if not booking_id:
        error_response = {'error': 'Missing required parameter: bookingId'}
        print(f"Validation error: {error_response}")
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup', 'HotelRoomBooking'),
                'apiPath': event.get('apiPath', '/bookings/{bookingId}/cancel'),
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

    # Log Bookings table schema for debugging
    try:
        table_description = dynamodb_client.describe_table(TableName='Bookings')
        key_schema = table_description['Table']['KeySchema']
        print(f"Bookings table schema: {key_schema}")
    except Exception as e:
        print(f"Error describing Bookings table: {str(e)}")

    # Check if booking exists in Bookings table using scan (fallback due to schema mismatch)
    try:
        bookings_table = dynamodb_resource.Table('Bookings')
        response = bookings_table.scan(
            FilterExpression='BookingId = :id',
            ExpressionAttributeValues={':id': booking_id}
        )
        items = response.get('Items', [])
        if not items:
            error_response = {'error': f'Booking with ID {booking_id} not found'}
            print(f"Booking not found: {error_response}")
            return {
                'messageVersion': '1.0',
                'response': {
                    'actionGroup': event.get('actionGroup', 'HotelRoomBooking'),
                    'apiPath': event.get('apiPath', '/bookings/{bookingId}/cancel'),
                    'httpMethod': event.get('httpMethod', 'POST'),
                    'httpStatusCode': 404,
                    'responseBody': {
                        'application/json': {
                            'body': json.dumps(error_response)
                        }
                    },
                    'sessionAttributes': event.get('sessionAttributes', {}),
                    'promptSessionAttributes': event.get('promptSessionAttributes', {})
                }
            }

        booking = items[0]  # Assume first item if multiple (should be unique)
        status = booking.get('Status', '')
        if status != 'Confirmed':
            error_response = {'error': f'Booking with ID {booking_id} is already {status}'}
            print(f"Invalid booking status: {error_response}")
            return {
                'messageVersion': '1.0',
                'response': {
                    'actionGroup': event.get('actionGroup', 'HotelRoomBooking'),
                    'apiPath': event.get('apiPath', '/bookings/{bookingId}/cancel'),
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

        # Extract booking details
        room_type = booking.get('RoomType', '')
        date = booking.get('Date', '')
        customer_name = booking.get('CustomerName', '')

    except Exception as e:
        error_response = {'error': f'Failed to check booking details: {str(e)}'}
        print(f"Error scanning Bookings: {error_response}")
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup', 'HotelRoomBooking'),
                'apiPath': event.get('apiPath', '/bookings/{bookingId}/cancel'),
                'httpMethod': event.get('httpMethod', 'POST'),
                'httpStatusCode': 500,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps(error_response)
                    }
                },
                'sessionAttributes': event.get('sessionAttributes', {}),
                'promptSessionAttributes': event.get('promptSessionAttributes', {})
            }
        }

    # Update booking status to Cancelled
    try:
        bookings_table.update_item(
            Key={
                'BookingId': booking_id,
                'Date': date  # Include sort key if required by schema
            },
            UpdateExpression='SET #status = :status',
            ExpressionAttributeNames={
                '#status': 'Status'
            },
            ExpressionAttributeValues={
                ':status': 'Cancelled'
            }
        )
    except Exception as e:
        error_response = {'error': f'Failed to cancel booking: {str(e)}'}
        print(f"Error updating booking status: {error_response}")
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup', 'HotelRoomBooking'),
                'apiPath': event.get('apiPath', '/bookings/{bookingId}/cancel'),
                'httpMethod': event.get('httpMethod', 'POST'),
                'httpStatusCode': 500,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps(error_response)
                    }
                },
                'sessionAttributes': event.get('sessionAttributes', {}),
                'promptSessionAttributes': event.get('promptSessionAttributes', {})
            }
        }

    # Update RoomAvailability by incrementing AvailableRooms
    try:
        dynamodb_client.update_item(
            TableName='RoomAvailability',
            Key={
                'RoomType': {'S': room_type},
                'Date': {'S': date}
            },
            UpdateExpression='SET AvailableRooms = AvailableRooms + :val',
            ExpressionAttributeValues={
                ':val': {'N': '1'}
            }
        )
    except Exception as e:
        print(f"Error updating RoomAvailability: {str(e)}")
        # Rollback booking status update
        try:
            bookings_table.update_item(
                Key={
                    'BookingId': booking_id,
                    'Date': date
                },
                UpdateExpression='SET #status = :status',
                ExpressionAttributeNames={
                    '#status': 'Status'
                },
                ExpressionAttributeValues={
                    ':status': 'Confirmed'
                }
            )
            error_response = {'error': f'Failed to update room availability, booking status reverted: {str(e)}'}
        except Exception as rollback_e:
            error_response = {'error': f'Failed to update room availability and rollback booking status: {str(rollback_e)}'}
        print(f"RoomAvailability update error: {error_response}")
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup', 'HotelRoomBooking'),
                'apiPath': event.get('apiPath', '/bookings/{bookingId}/cancel'),
                'httpMethod': event.get('httpMethod', 'POST'),
                'httpStatusCode': 500,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps(error_response)
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
        'status': 'Cancelled'
    }
    print(f"Success: Booking cancelled, response: {response_body}")

    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': event.get('actionGroup', 'HotelRoomBooking'),
            'apiPath': event.get('apiPath', '/bookings/{bookingId}/cancel'),
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
