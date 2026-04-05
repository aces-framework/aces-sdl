use std::path::PathBuf;

use crate::{
    errors::RangerError,
    middleware::{authentication::UserInfo, order::OrderInfo},
    models::{
        helpers::uuid::Uuid, CustomElementRest, EnvironmentRest, Order, PlotRest, StructureRest,
        TrainingObjectiveRest,
    },
    services::database::order::{
        DeleteCustomElement, DeleteEnvironment, DeletePlot, DeleteStructure,
        DeleteTrainingObjective, GetCustomElement, GetOrders, UpsertCustomElement,
        UpsertEnvironment, UpsertPlot, UpsertStructure, UpsertTrainingObjective,
    },
    utilities::{create_database_error_handler, create_mailbox_error_handler, save_file},
    AppState,
};
use actix_multipart::Multipart;
use actix_web::{
    delete, get, post, put,
    web::{Data, Json, Path},
    HttpResponse,
};
use anyhow::Result;
use log::{debug, error};

#[get("")]
pub async fn get_orders_client(
    app_state: Data<AppState>,
    user_info: UserInfo,
) -> Result<Json<Vec<Order>>, RangerError> {
    let client_id = user_info.email.clone().ok_or_else(|| {
        error!("Client id not found");
        RangerError::UserInfoMissing
    })?;

    let orders = app_state
        .database_address
        .send(GetOrders)
        .await
        .map_err(create_mailbox_error_handler("Database for orders"))?
        .map_err(create_database_error_handler("Get orders"))?
        .into_iter()
        .filter(|order| order.is_owner(&client_id))
        .collect();

    Ok(Json(orders))
}

#[post("/training_objective")]
pub async fn create_training_objective(
    order: OrderInfo,
    app_state: Data<AppState>,
    new_training_objectives: Json<TrainingObjectiveRest>,
) -> Result<Json<TrainingObjectiveRest>, RangerError> {
    app_state
        .database_address
        .send(UpsertTrainingObjective(
            order.id,
            None,
            new_training_objectives.clone(),
        ))
        .await
        .map_err(create_mailbox_error_handler(
            "Database for training objectives",
        ))?
        .map_err(create_database_error_handler("Upsert training objective"))?;

    Ok(Json(new_training_objectives.into_inner()))
}

#[put("/training_objective/{training_objective_uuid}")]
pub async fn update_training_objective(
    order: OrderInfo,
    path_variable: Path<(Uuid, Uuid)>,
    app_state: Data<AppState>,
    new_training_objective: Json<TrainingObjectiveRest>,
) -> Result<Json<TrainingObjectiveRest>, RangerError> {
    let (_, training_objective_uuid) = path_variable.into_inner();
    app_state
        .database_address
        .send(UpsertTrainingObjective(
            order.id,
            Some(training_objective_uuid),
            new_training_objective.clone(),
        ))
        .await
        .map_err(create_mailbox_error_handler(
            "Database for training objectives",
        ))?
        .map_err(create_database_error_handler("Upsert training objective"))?;

    Ok(Json(new_training_objective.into_inner()))
}

#[delete("/training_objective/{training_objective_uuid}")]
pub async fn delete_training_objective(
    _order: OrderInfo,
    path_variable: Path<(Uuid, Uuid)>,
    app_state: Data<AppState>,
) -> Result<Json<Uuid>, RangerError> {
    let (_, training_objective_uuid) = path_variable.into_inner();
    app_state
        .database_address
        .send(DeleteTrainingObjective(training_objective_uuid))
        .await
        .map_err(create_mailbox_error_handler(
            "Database for training objectives",
        ))?
        .map_err(create_database_error_handler("Delete training objective"))?;

    Ok(Json(training_objective_uuid))
}

#[post("/structure")]
pub async fn create_structure(
    order: OrderInfo,
    app_state: Data<AppState>,
    new_structure: Json<StructureRest>,
) -> Result<Json<StructureRest>, RangerError> {
    app_state
        .database_address
        .send(UpsertStructure(order.id, None, new_structure.clone()))
        .await
        .map_err(create_mailbox_error_handler(
            "Database for client order structures",
        ))?
        .map_err(create_database_error_handler("Create structure"))?;

    Ok(Json(new_structure.into_inner()))
}

#[delete("/structure/{structure_uuid}")]
pub async fn delete_structure(
    _order: OrderInfo,
    path_variable: Path<(Uuid, Uuid)>,
    app_state: Data<AppState>,
) -> Result<Json<Uuid>, RangerError> {
    let (_, structure_uuid) = path_variable.into_inner();
    app_state
        .database_address
        .send(DeleteStructure(structure_uuid))
        .await
        .map_err(create_mailbox_error_handler("Database for structures"))?
        .map_err(create_database_error_handler("Delete structure"))?;

    Ok(Json(structure_uuid))
}

#[put("/structure/{structure_uuid}")]
pub async fn update_structure(
    order: OrderInfo,
    path_variable: Path<(Uuid, Uuid)>,
    app_state: Data<AppState>,
    new_structure: Json<StructureRest>,
) -> Result<Json<StructureRest>, RangerError> {
    let (_, structure_uuid) = path_variable.into_inner();
    app_state
        .database_address
        .send(UpsertStructure(
            order.id,
            Some(structure_uuid),
            new_structure.clone(),
        ))
        .await
        .map_err(create_mailbox_error_handler("Database for structure"))?
        .map_err(create_database_error_handler("Upsert structure"))?;

    Ok(Json(new_structure.into_inner()))
}

#[post("/environment")]
pub async fn create_environment(
    order: OrderInfo,
    app_state: Data<AppState>,
    new_environment: Json<EnvironmentRest>,
) -> Result<Json<EnvironmentRest>, RangerError> {
    app_state
        .database_address
        .send(UpsertEnvironment(order.id, None, new_environment.clone()))
        .await
        .map_err(create_mailbox_error_handler(
            "Database for order environments",
        ))?
        .map_err(create_database_error_handler("Upsert order environments"))?;

    Ok(Json(new_environment.into_inner()))
}

#[put("/environment/{environment_uuid}")]
pub async fn update_environment(
    order: OrderInfo,
    path_variable: Path<(Uuid, Uuid)>,
    app_state: Data<AppState>,
    new_environment: Json<EnvironmentRest>,
) -> Result<Json<EnvironmentRest>, RangerError> {
    let (_, environment_uuid) = path_variable.into_inner();
    app_state
        .database_address
        .send(UpsertEnvironment(
            order.id,
            Some(environment_uuid),
            new_environment.clone(),
        ))
        .await
        .map_err(create_mailbox_error_handler(
            "Database for order environments",
        ))?
        .map_err(create_database_error_handler("Upsert order environments"))?;

    Ok(Json(new_environment.into_inner()))
}

#[delete("/environment/{environment_uuid}")]
pub async fn delete_environment(
    _order: OrderInfo,
    path_variable: Path<(Uuid, Uuid)>,
    app_state: Data<AppState>,
) -> Result<Json<Uuid>, RangerError> {
    let (_, environment_uuid) = path_variable.into_inner();
    app_state
        .database_address
        .send(DeleteEnvironment(environment_uuid))
        .await
        .map_err(create_mailbox_error_handler("Database for environments"))?
        .map_err(create_database_error_handler("Delete environment"))?;

    Ok(Json(environment_uuid))
}

#[post("/custom_element")]
pub async fn create_custom_element(
    order: OrderInfo,
    app_state: Data<AppState>,
    new_custom_element: Json<CustomElementRest>,
) -> Result<Json<CustomElementRest>, RangerError> {
    app_state
        .database_address
        .send(UpsertCustomElement(
            order.id,
            None,
            new_custom_element.clone(),
        ))
        .await
        .map_err(create_mailbox_error_handler(
            "Database for order custom elements",
        ))?
        .map_err(create_database_error_handler("Upsert order custom element"))?;

    Ok(Json(new_custom_element.into_inner()))
}

#[put("/custom_element/{custom_element_uuid}")]
pub async fn update_custom_element(
    order: OrderInfo,
    path_variable: Path<(Uuid, Uuid)>,
    app_state: Data<AppState>,
    new_custom_element: Json<CustomElementRest>,
) -> Result<Json<CustomElementRest>, RangerError> {
    let (_, custom_element_uuid) = path_variable.into_inner();
    app_state
        .database_address
        .send(UpsertCustomElement(
            order.id,
            Some(custom_element_uuid),
            new_custom_element.clone(),
        ))
        .await
        .map_err(create_mailbox_error_handler(
            "Database for order custom elements",
        ))?
        .map_err(create_database_error_handler("Upsert order custom element"))?;

    Ok(Json(new_custom_element.into_inner()))
}

#[post("/custom_element/{custom_element_uuid}/file")]
pub async fn upload_custom_element_file(
    _order: OrderInfo,
    path_variable: Path<(Uuid, Uuid)>,
    app_state: Data<AppState>,
    payload: Multipart,
) -> Result<HttpResponse, RangerError> {
    let (_, custom_element_uuid) = path_variable.into_inner();
    let custom_element_option = app_state
        .database_address
        .send(GetCustomElement(custom_element_uuid))
        .await
        .map_err(create_mailbox_error_handler(
            "Database for order custom elements",
        ))?
        .map_err(create_database_error_handler("Get order custom element"))?;
    let storage_path = app_state.configuration.file_storage_path.clone();

    match custom_element_option {
        Some(custom_element) => {
            let file_path = PathBuf::from(storage_path).join(custom_element.id.to_string());
            save_file(payload, &file_path).await.map_err(|err| {
                error!("File upload failed: {:?}", err);
                RangerError::FileUploadFailed
            })?;
            debug!("File uploaded");
        }
        None => {
            error!("Custom element not found");
            return Err(RangerError::CustomElementNotFound);
        }
    }

    Ok(HttpResponse::Ok().into())
}

#[get("/custom_element/{custom_element_uuid}/file")]
pub async fn get_custom_element_file(
    _order: OrderInfo,
    path_variable: Path<(Uuid, Uuid)>,
    app_state: Data<AppState>,
) -> Result<HttpResponse, RangerError> {
    let (_, custom_element_uuid) = path_variable.into_inner();
    let custom_element_option = app_state
        .database_address
        .send(GetCustomElement(custom_element_uuid))
        .await
        .map_err(create_mailbox_error_handler(
            "Database for order custom elements",
        ))?
        .map_err(create_database_error_handler("Get order custom element"))?;
    let storage_path = app_state.configuration.file_storage_path.clone();

    match custom_element_option {
        Some(custom_element) => {
            let file_path = PathBuf::from(storage_path).join(custom_element.id.to_string());
            Ok(
                HttpResponse::Ok().body(std::fs::read(file_path).map_err(|err| {
                    error!("File read failed: {:?}", err);
                    if err.kind() == std::io::ErrorKind::NotFound {
                        return RangerError::FileNotFound;
                    }
                    RangerError::FileReadFailed
                })?),
            )
        }
        None => {
            error!("Custom element not found");
            Err(RangerError::CustomElementNotFound)
        }
    }
}

#[delete("/custom_element/{custom_element_uuid}/file")]
pub async fn delete_custom_element_file(
    _order: OrderInfo,
    path_variable: Path<(Uuid, Uuid)>,
    app_state: Data<AppState>,
) -> Result<Json<Uuid>, RangerError> {
    let (_, custom_element_uuid) = path_variable.into_inner();
    let custom_element_option = app_state
        .database_address
        .send(GetCustomElement(custom_element_uuid))
        .await
        .map_err(create_mailbox_error_handler(
            "Database for order custom elements",
        ))?
        .map_err(create_database_error_handler("Get order custom element"))?;
    let storage_path = app_state.configuration.file_storage_path.clone();

    match custom_element_option {
        Some(custom_element) => {
            let file_path = PathBuf::from(storage_path).join(custom_element.id.to_string());
            std::fs::remove_file(file_path).map_err(|err| {
                error!("File deletion failed: {:?}", err);
                RangerError::FileDeletionFailed
            })?;
            debug!("File deleted");
        }
        None => {
            error!("Custom element not found");
            return Err(RangerError::CustomElementNotFound);
        }
    }

    Ok(Json(custom_element_uuid))
}

#[delete("/custom_element/{custom_element_uuid}")]
pub async fn delete_custom_element(
    _order: OrderInfo,
    path_variable: Path<(Uuid, Uuid)>,
    app_state: Data<AppState>,
) -> Result<Json<Uuid>, RangerError> {
    let (_, custom_element_uuid) = path_variable.into_inner();
    app_state
        .database_address
        .send(DeleteCustomElement(custom_element_uuid))
        .await
        .map_err(create_mailbox_error_handler("Database for custom elements"))?
        .map_err(create_database_error_handler("Delete custom element"))?;

    Ok(Json(custom_element_uuid))
}

#[post("/plot")]
pub async fn create_plot(
    order: OrderInfo,
    app_state: Data<AppState>,
    new_plot: Json<PlotRest>,
) -> Result<Json<PlotRest>, RangerError> {
    app_state
        .database_address
        .send(UpsertPlot(order.id, None, new_plot.clone()))
        .await
        .map_err(create_mailbox_error_handler("Database for order plots"))?
        .map_err(create_database_error_handler("Upsert order plot"))?;

    Ok(Json(new_plot.into_inner()))
}

#[put("/plot/{plot_uuid}")]
pub async fn update_plot(
    order: OrderInfo,
    path_variable: Path<(Uuid, Uuid)>,
    app_state: Data<AppState>,
    new_plot: Json<PlotRest>,
) -> Result<Json<PlotRest>, RangerError> {
    let (_, plot_uuid) = path_variable.into_inner();
    app_state
        .database_address
        .send(UpsertPlot(order.id, Some(plot_uuid), new_plot.clone()))
        .await
        .map_err(create_mailbox_error_handler("Database for order plots"))?
        .map_err(create_database_error_handler("Upsert order plot"))?;

    Ok(Json(new_plot.into_inner()))
}

#[delete("/plot/{plot_uuid}")]
pub async fn delete_plot(
    _order: OrderInfo,
    path_variable: Path<(Uuid, Uuid)>,
    app_state: Data<AppState>,
) -> Result<Json<Uuid>, RangerError> {
    let (_, plot_uuid) = path_variable.into_inner();
    app_state
        .database_address
        .send(DeletePlot(plot_uuid))
        .await
        .map_err(create_mailbox_error_handler("Database for plots"))?
        .map_err(create_database_error_handler("Delete plot"))?;

    Ok(Json(plot_uuid))
}
