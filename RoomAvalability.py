import json
import boto3

# Create DynamoDB client
client = boto3.client('dynamodb')

def lambda_handler(event, context):
    # Log the user input
    print(f"The user input is {event}")

    # Extract date from parameters
    user_input_date = event['parameters'][0]['value']

    # Query DynamoDB for each room type
    room_types = ['Single', 'Double', 'Suite']
    results = []

    for room_type in room_types:
        response = client.get_item(
            TableName='RoomAvailability',
            Key={
                'RoomType': {'S': room_type},
                'Date': {'S': user_input_date}
            }
        )
        item = response.get('Item', {})
        results.append({
            'roomType': room_type,
            'date': user_input_date,
            'availableRooms': int(item['AvailableRooms']['N']) if 'AvailableRooms' in item else 0,
            'price': float(item['Price']['N']) if 'Price' in item else 0.0
        })
        print(f"Room inventory data for {room_type}: {item}")

    # Format response for Bedrock Agent Action Group
    agent = event['agent']
    actionGroup = event['actionGroup']
    api_path = event['apiPath']

    response_body = {
        'application/json': {
            'body': json.dumps(results)
        }
    }
    print(f"The response to agent is {response_body}")

    action_response = {
        'actionGroup': actionGroup,
        'apiPath': api_path,
        'httpMethod': event['httpMethod'],
        'httpStatusCode': 200,
        'responseBody': response_body
    }

    api_response = {
        'messageVersion': '1.0',
        'response': action_response,
        'sessionAttributes': event['sessionAttributes'],
        'promptSessionAttributes': event['promptSessionAttributes']
    }

    print(f"The final response is {api_response}")
    return api_response
