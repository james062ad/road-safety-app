from flask import Blueprint, request, jsonify
import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import os

# Create blueprint for API routes
api = Blueprint('api', __name__)

# Input validators
INPUT_VALIDATORS = {
    'road_type': {
        'options': [1, 2, 3, 6],
        'required': True,
        'error': 'Please select a valid road type (1: Residential, 2: Suburban, 3: Rural, 6: Urban)'
    },
    'weather_conditions': {
        'options': ['Fine', 'Rain', 'Snow', 'Fog'],
        'required': True,
        'error': 'Please select valid weather conditions'
    },
    'speed_limit': {
        'options': [20, 30, 40, 50, 60, 70],
        'required': True,
        'error': 'Please select a valid speed limit'
    },
    'time_of_day': {
        'options': ['Morning', 'Afternoon', 'Evening', 'Night'],
        'required': True,
        'error': 'Please select a valid time of day'
    },
    'junction_detail': {
        'options': ['T Junction', 'Crossroads', 'Roundabout', 'Not at junction'],
        'required': True,
        'error': 'Please select a valid junction type'
    }
}

# Risk level thresholds - binary classification
RISK_THRESHOLDS = {
    'high': 0.70    # Threshold for high risk classification
}

# Get the directory containing the current file
current_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(os.path.dirname(current_dir), 'models', 'best_model.joblib')

# Load the model and scaler
try:
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found at {model_path}")
        
    model_artifacts = joblib.load(model_path)
    if not isinstance(model_artifacts, dict) or 'model' not in model_artifacts:
        raise ValueError("Invalid model file format")
        
    model = model_artifacts['model']
    feature_names = model_artifacts.get('feature_names', [])
    print("Model loaded successfully")
    print(f"Feature names: {feature_names}")
    # Initialize a new scaler for each prediction
    scaler = StandardScaler()
except Exception as e:
    print(f"Error loading model: {str(e)}")
    model = None
    feature_names = []
    scaler = None

def validate_input(data):
    """Validate input data against defined validators"""
    errors = {}
    for field, rules in INPUT_VALIDATORS.items():
        if rules['required'] and field not in data:
            errors[field] = rules['error']
        elif field in data and data[field] not in rules['options']:
            errors[field] = f"Invalid value for {field}. Options are: {rules['options']}"
    return errors

def calculate_risk_factors(data):
    """Calculate additional risk factors based on conditions"""
    risk_factors = []
    
    # Time-based risks
    if data['time_of_day'] in ['Night', 'Evening']:
        risk_factors.append('Limited visibility during night/evening hours')
    
    # Weather-based risks
    if data['weather_conditions'] != 'Fine':
        risk_factors.append(f"Adverse weather conditions ({data['weather_conditions']})")
    
    # Speed-based risks
    if data['speed_limit'] > 40:
        risk_factors.append('High speed zone')
    
    # Junction-based risks
    if data['junction_detail'] != 'Not at junction':
        risk_factors.append(f"Complex junction type ({data['junction_detail']})")
    
    # Road type risks with adjusted descriptions
    road_type_desc = {
        6: 'Urban area with high traffic',
        3: 'Rural road with potential hazards',
        2: 'Suburban area with moderate traffic',
        1: 'Residential area with lower traffic'
    }
    if data['road_type'] in road_type_desc:
        if data['road_type'] in [6, 3]:  # Only add as risk factor for higher-risk road types
            risk_factors.append(road_type_desc[data['road_type']])
    
    return risk_factors

def preprocess_input(data):
    """Preprocess input data for model prediction"""
    # Create DataFrame with input data
    df = pd.DataFrame([data])
    
    # Initialize all features to 0
    for feature in feature_names:
        df[feature] = 0
    
    # Create one-hot encoded columns for road_type
    road_type = df['road_type'].values[0]
    df[f'road_type_{road_type}'] = 1
    
    # Map weather conditions to numeric codes
    weather_map = {'Fine': 1, 'Rain': 2, 'Snow': 3, 'Fog': 4}
    weather_code = weather_map.get(df['weather_conditions'].values[0], 1)
    df[f'weather_conditions_{weather_code}'] = 1
    
    # Map time of day to light conditions
    time_to_light = {
        'Morning': 1,  # Daylight
        'Afternoon': 1,  # Daylight
        'Evening': 4,  # Darkness - lights lit
        'Night': 4,    # Darkness - lights lit
    }
    light_code = time_to_light.get(df['time_of_day'].values[0], 1)
    df[f'light_conditions_{light_code}'] = 1
    
    # Map junction detail
    junction_map = {
        'Not at junction': 0,
        'T Junction': 1,
        'Crossroads': 2,
        'Roundabout': 3
    }
    junction_code = junction_map.get(df['junction_detail'].values[0], 0)
    df[f'junction_detail_{junction_code}'] = 1
    
    # Add speed limit (normalized)
    df['speed_limit'] = df['speed_limit'].astype(float) / 70.0  # Normalize by max speed
    
    # Add derived risk factors
    df['number_of_vehicles'] = 1
    df['number_of_casualties'] = 0
    df['casualty_rate'] = 0
    df['weather_risk'] = 1 if df['weather_conditions'].values[0] != 'Fine' else 0
    df['surface_risk'] = 1 if df['weather_conditions'].values[0] in ['Rain', 'Snow'] else 0
    df['combined_risk'] = df['weather_risk'] + df['surface_risk']
    df['is_night'] = 1 if df['time_of_day'].values[0] in ['Night', 'Evening'] else 0
    df['is_rush_hour'] = 1 if df['time_of_day'].values[0] in ['Morning', 'Evening'] else 0
    df['is_weekend'] = 0
    df['high_speed'] = 1 if df['speed_limit'].values[0] > 40 else 0
    df['night_speed_risk'] = df['is_night'] * df['high_speed']
    df['weather_speed_risk'] = df['weather_risk'] * df['high_speed']
    
    # Print preprocessed features for debugging
    print("Preprocessed features:")
    print(df[feature_names])
    
    return df[feature_names]

def adjust_probability(prob):
    """Adjust probability using a more aggressive transformation"""
    # First, adjust for the scale_pos_weight bias
    adjusted = (prob * 0.5) / (prob * 0.5 + (1 - prob))
    
    # Apply a more aggressive transformation
    if adjusted > 0.5:
        # Map probabilities from [0.5, 1] to [0.2, 0.9] using a power transformation
        normalized = (adjusted - 0.5) * 2  # Scale to [0, 1]
        transformed = pow(normalized, 5)  # Apply fifth power to spread values even more
        final_prob = 0.2 + (transformed * 0.7)  # Scale to [0.2, 0.9]
    else:
        # Map probabilities from [0, 0.5] to [0, 0.2] using cube root for smoother transition
        normalized = adjusted * 2  # Scale to [0, 1]
        final_prob = 0.2 * pow(normalized, 0.33)  # Scale to [0, 0.2] with cube root
    
    # Add risk-based adjustments with reduced impact for low probabilities
    base_diff = abs(prob - 0.5)
    if final_prob < 0.4:  # Reduce impact for lower probabilities
        final_prob += base_diff * 0.02
    else:
        final_prob += base_diff * 0.05
    
    return min(max(final_prob, 0), 1)  # Ensure probability stays between 0 and 1

def generate_recommendations(data, risk_level, risk_factors):
    """Generate specific recommendations based on risk factors"""
    recommendations = []
    
    if risk_level == "High Risk":
        if data['speed_limit'] > 40:
            recommendations.append("Consider reducing speed limit in this area")
        if data['junction_detail'] != 'Not at junction':
            recommendations.append("Install traffic monitoring cameras at the junction")
        if data['time_of_day'] in ['Night', 'Evening']:
            recommendations.append("Improve street lighting conditions")
        if data['weather_conditions'] != 'Fine':
            recommendations.append(f"Install weather warning signs for {data['weather_conditions']} conditions")
        if len(risk_factors) > 0:
            recommendations.append("Increase police patrols in the area")
    
    else:  # Not High Risk
        if data['junction_detail'] != 'Not at junction':
            recommendations.append("Consider additional signage at the junction")
        if data['weather_conditions'] != 'Fine':
            recommendations.append("Ensure regular road maintenance")
        if data['time_of_day'] in ['Night', 'Evening']:
            recommendations.append("Consider enhanced road markings")
        if len(risk_factors) > 0:
            recommendations.append("Monitor conditions and maintain current safety measures")
        else:
            recommendations.append("Continue regular maintenance and monitoring")
        if data['road_type'] == 1:
            recommendations.append("Maintain residential area safety features")
        if data['speed_limit'] <= 30:
            recommendations.append("Current speed restrictions are appropriate")
    
    return recommendations if recommendations else ["No specific recommendations needed at this time"]

@api.route('/predict', methods=['POST'])
def predict():
    """
    Endpoint for making predictions
    Expects JSON data with features
    Returns prediction and probability
    """
    if model is None:
        return jsonify({"error": "Model not loaded. Please try again later."}), 500

    try:
        # Get data from request
        data = request.get_json()

        # Validate input data
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        validation_errors = validate_input(data)
        if validation_errors:
            return jsonify({
                "error": "Invalid input data",
                "details": validation_errors
            }), 400

        # Preprocess input data
        processed_data = preprocess_input(data)
        
        # Make prediction
        raw_probability = model.predict_proba(processed_data)[0, 1]
        print(f"Raw prediction probability: {raw_probability}")
        
        # Calculate base risk score from input features
        base_risk_score = 0
        if data['speed_limit'] > 40:
            base_risk_score += 0.1
        if data['time_of_day'] in ['Night', 'Evening']:
            base_risk_score += 0.1
        if data['weather_conditions'] != 'Fine':
            base_risk_score += 0.1
        if data['junction_detail'] != 'Not at junction':
            base_risk_score += 0.1
        if data['road_type'] in [6, 3]:
            base_risk_score += 0.1
        
        # Adjust probability for model bias
        adjusted_probability = adjust_probability(raw_probability)
        
        # Blend with base risk score
        final_probability = (adjusted_probability * 0.7) + (base_risk_score * 0.3)
        print(f"Adjusted prediction probability: {final_probability}")
        
        # Determine risk level based on probability threshold
        risk_level = "High Risk" if final_probability > RISK_THRESHOLDS['high'] else "Not High Risk"
        
        # Calculate risk factors
        risk_factors = calculate_risk_factors(data)
        
        # Generate recommendations
        recommendations = generate_recommendations(data, risk_level, risk_factors)
        
        return jsonify({
            "prediction": {
                "risk_level": risk_level,
                "probability": f"{final_probability:.2%}",
                "raw_probability": f"{raw_probability:.2%}",
                "risk_factors": risk_factors,
                "recommendations": recommendations
            },
            "input_data": data
        }), 200

    except Exception as e:
        print(f"Prediction error: {str(e)}")
        return jsonify({"error": "Failed to process prediction"}), 500 