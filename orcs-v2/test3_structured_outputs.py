import os
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from typing import List

# Load environment variables
load_dotenv()

# More complex nested schemas
class Variable(BaseModel):
    name: str
    value: float
    unit: str

class Operation(BaseModel):
    operation_type: str
    left_operand: str
    right_operand: str
    result: str

class Step(BaseModel):
    explanation: str
    operation: Operation
    variables: list[Variable]
    intermediate_result: float

class Solution(BaseModel):
    equation_type: str
    initial_variables: list[Variable]
    steps: list[Step]
    final_answer: float
    verification: str

def test_complex_schema():
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OpenAI API key not found in environment variables")
    
    client = OpenAI(api_key=api_key)
    
    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {
                    "role": "system",
                    "content": "You are a math tutor who provides detailed step-by-step solutions with intermediate calculations and variable tracking."
                },
                {
                    "role": "user",
                    "content": "Solve this system of equations: 3x + 2y = 12, 5x - y = 7"
                }
            ],
            response_format=Solution
        )
        
        solution = completion.choices[0].message.parsed
        
        print("\n=== Complex Math Solution ===")
        print(f"Equation Type: {solution.equation_type}")
        
        print("\nInitial Variables:")
        for var in solution.initial_variables:
            print(f"- {var.name}: {var.value} {var.unit}")
        
        print("\nSolution Steps:")
        for i, step in enumerate(solution.steps, 1):
            print(f"\nStep {i}:")
            print(f"Explanation: {step.explanation}")
            print(f"Operation: {step.operation.operation_type}")
            print(f"  {step.operation.left_operand} {step.operation.operation_type} {step.operation.right_operand} = {step.operation.result}")
            print("Current Variables:")
            for var in step.variables:
                print(f"  - {var.name}: {var.value} {var.unit}")
            print(f"Intermediate Result: {step.intermediate_result}")
        
        print(f"\nFinal Answer: {solution.final_answer}")
        print(f"Verification: {solution.verification}")
        
    except Exception as e:
        print(f"\nError occurred: {str(e)}")
        raise

if __name__ == "__main__":
    test_complex_schema()