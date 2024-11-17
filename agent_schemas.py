from pydantic import BaseModel, Field, StrictStr
from typing import List

class MovieBody(BaseModel):
    theater_name: StrictStr = Field(..., description="The name of the theater.")
    movie_name: StrictStr = Field(..., description="The name of the movie.")
    show_times: list[StrictStr] = Field(..., description="A list of times when the movie is showing.")
    theater_address: StrictStr = Field(..., description="The address of the theater.")

class MovieListResponse(BaseModel):
    theaters: List[MovieBody] = Field(..., description="List of theaters and their movie showings.")