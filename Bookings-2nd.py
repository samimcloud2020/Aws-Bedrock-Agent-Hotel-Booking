import json
import boto3
import uuid
from datetime import datetime

# Create DynamoDB client
dynamodb = boto3.client('dynamodb')

def lambda_handler(event, context):
    customer_name = event["requestBody"]['content']['application/json']['properties'][0]['value']
    date = event["requestBody"]['content']['application/json']['properties'][1]['value']
    room_type = event["requestBody"]['content']['application/json']['properties'][2]['value']
    print(f" The Customer name is {customer_name} & date is {date} & room type is {room_type}")
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
        print(f" The item is {item}")
        available_rooms = item['AvailableRooms']['N']
        print(f" The available rooms are {available_rooms}")
    except Exception as e:
        print(f"Error querying RoomAvailability: {str(e)}")

    # Verify if room is available
    if int(available_rooms) > 0:
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

    agent = event['agent']
    actionGroup = event['actionGroup']
    api_path = event['apiPath']
    # get parameters
    #get_parameters = event.get('parameters', [])
    # post parameters
    post_parameters = event['requestBody']['content']['application/json']['properties']

    response_body = {
        'application/json': {
            'body': json.dumps(booking_id)
        }
    }
    
    action_response = {
        'actionGroup': event['actionGroup'],
        'apiPath': event['apiPath'],
        'httpMethod': event['httpMethod'],
        'httpStatusCode': 200,
        'responseBody': response_body
    }
    
    session_attributes = event['sessionAttributes']
    prompt_session_attributes = event['promptSessionAttributes']
    
    api_response = {
        'messageVersion': '1.0', 
        'response': action_response,
        'sessionAttributes': session_attributes,
        'promptSessionAttributes': prompt_session_attributes
    }
    print(f" The api response is {api_response}")
    return api_response
