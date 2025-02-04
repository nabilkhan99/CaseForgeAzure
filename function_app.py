import azure.functions as func
from functions.capabilities import main as capabilities_main
from functions.generate_review import main as generate_review_main
from functions.improve_review import main as improve_review_main
from functions.improve_section import main as improve_section_main
import logging
app = func.FunctionApp()

@app.function_name(name="capabilities")
@app.route(route="capabilities", auth_level=func.AuthLevel.ANONYMOUS)
async def capabilities(req: func.HttpRequest) -> func.HttpResponse:
    return await capabilities_main(req)

@app.function_name(name="generate-review")
@app.route(route="generate-review", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
async def generate_review(req: func.HttpRequest) -> func.HttpResponse:
    return await generate_review_main(req)

@app.function_name(name="improve-review")
@app.route(route="improve-review", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
async def improve_review(req: func.HttpRequest) -> func.HttpResponse:
    return await improve_review_main(req)

@app.function_name(name="improve-section")
@app.route(route="improve-section", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
async def improve_section(req: func.HttpRequest) -> func.HttpResponse:
    return await improve_section_main(req)

