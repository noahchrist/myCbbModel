from pydantic import BaseModel
from fastapi import HTTPException
from supabase import Client
from typing import Optional

class ModelCreate(BaseModel):
    modelName: str
    bettingStyle: str
    tenDigit: int
    weights: dict
    rejectedNames: list

async def get_model_names(supabase: Client):
    """Get 5 random available model names"""
    response = supabase.table('model_names').select('model_name').is_('user_id', 'null').limit(5).execute()
    names = [row['model_name'] for row in response.data]
    return {"names": names}

async def create_model(request: ModelCreate, user_id: str, supabase: Client):
    """Create a new model (placeholder - will implement training logic later)"""
    # TODO: Implement model training and storage logic
    raise HTTPException(status_code=501, detail="Model creation not yet implemented")

async def delete_model(model_id: int, user_id: str, supabase: Client):
    """Soft delete a model by clearing model_path"""
    try:
        # Get model details
        response = supabase.table('model_details').select('model_name, model_path').eq('model_id', model_id).eq('user_id', user_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Model not found")
        
        model_name = response.data[0]['model_name']
        
        # Soft delete: clear model_path but keep record for historical accuracy
        supabase.table('model_details').update({'model_path': None}).eq('model_id', model_id).eq('user_id', user_id).execute()
        supabase.table('model_names').update({'user_id': None}).eq('model_name', model_name).eq('user_id', user_id).execute()
        
        return {"message": "Model deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting model: {str(e)}")

async def get_model_data(model_id: int, user_id: str, supabase: Client, date: Optional[str] = None):
    """
    Get comprehensive model data including details, predictions, and performance.
    If date is provided, only return predictions for that date.
    """
    try:
        # Get model details
        model_response = supabase.table('model_details').select('''
            model_id, model_name, created_datetime, betting_style, ten_digit,
            weight_gen_off, weight_gen_def, weight_pace, weight_threes, weight_fts,
            weight_per_def, weight_int_def, weight_boards, weight_playmaking, weight_intangibles,
            model_path
        ''').eq('model_id', model_id).execute()
        
        if not model_response.data:
            raise HTTPException(status_code=404, detail="Model not found")
        
        model = model_response.data[0]
        
        # Verify ownership for non-community models
        if model.get('user_id') and model.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Build predictions query
        predictions_query = supabase.table('model_predictions').select('*').eq('model_id', model_id)
        
        if date:
            # Get predictions for specific date
            predictions_query = predictions_query.eq('game_date', date)
        else:
            # Get all completed predictions for history
            predictions_query = predictions_query.eq('is_completed', True).order('game_date', desc=True)
        
        predictions_response = predictions_query.execute()
        
        # Format predictions
        predictions = []
        total_wins = 0
        total_losses = 0
        total_units_bet = 0
        total_units_won = 0
        
        for pred in predictions_response.data:
            if pred.get('is_completed'):
                # Calculate stats
                if pred.get('is_won'):
                    total_wins += 1
                else:
                    total_losses += 1
                
                total_units_bet += pred.get('units_bet', 0) or 0
                total_units_won += pred.get('units_won', 0) or 0
            
            predictions.append({
                "predictionId": pred['prediction_id'],
                "gameId": pred['game_id'],
                "gameDate": pred['game_date'],
                "homeTeam": pred['home_team_name'],
                "awayTeam": pred['away_team_name'],
                "predictedPtDiff": pred['predicted_pt_diff'],
                "predictedPtTotal": pred['predicted_pt_total'],
                "predictedEdge": pred['predicted_edge'],
                "predictionSummary": pred['prediction_summary'],
                "isCompleted": pred['is_completed'],
                "isWon": pred['is_won'],
                "unitsBet": pred['units_bet'],
                "unitsWon": pred['units_won']
            })
        
        # Calculate ROI
        roi = (total_units_won / total_units_bet * 100) if total_units_bet > 0 else 0
        
        return {
            "model": {
                "id": model['model_id'],
                "modelName": model['model_name'],
                "dateCreated": model['created_datetime'],
                "bettingStyle": model['betting_style'],
                "tenDigit": model['ten_digit'],
                "isActive": model['model_path'] is not None,
                "weights": {
                    "weightGenOff": model['weight_gen_off'],
                    "weightGenDef": model['weight_gen_def'],
                    "weightPace": model['weight_pace'],
                    "weightThrees": model['weight_threes'],
                    "weightFts": model['weight_fts'],
                    "weightPerDef": model['weight_per_def'],
                    "weightIntDef": model['weight_int_def'],
                    "weightBoards": model['weight_boards'],
                    "weightPlaymaking": model['weight_playmaking'],
                    "weightIntangibles": model['weight_intangibles']
                }
            },
            "performance": {
                "wins": total_wins,
                "losses": total_losses,
                "unitsBet": round(total_units_bet, 2),
                "unitsWon": round(total_units_won, 2),
                "roi": round(roi, 1)
            },
            "predictions": predictions
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching model data: {str(e)}")
