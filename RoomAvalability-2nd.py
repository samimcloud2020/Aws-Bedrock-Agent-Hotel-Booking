import json
import boto3

# Create DynamoDB client
client = boto3.client('dynamodb')

def lambda_handler(event, context):
    # Log the user input
    print(f"The user input is {event}")
    user_input_date = event['parameters'][0]['value']
    print(f"The date is {user_input_date}")

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
        print(f"The Item is {item}")
        results.append({
            'roomType': room_type,
            'date': user_input_date,
            'availableRooms': int(item['AvailableRooms']['N']) if 'AvailableRooms' in item else 0,
            'price': float(item['Price']['N']) if 'Price' in item else 0.0
        })
        print(f"Room inventory data for {room_type}: {item}")
        agent = event['agent']
    actionGroup = event['actionGroup']
    api_path = event['apiPath']
    # get parameters
    get_parameters = event.get('parameters', [])
    # post parameters
    #post_parameters = event['requestBody']['content']['application/json']['properties']

    response_body = {
        'application/json': {
            'body': json.dumps(results)
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
    print(f"The final response is {api_response}")    
    return api_response
