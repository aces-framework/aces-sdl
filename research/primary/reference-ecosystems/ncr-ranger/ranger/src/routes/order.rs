use crate::{
    errors::RangerError,
    middleware::{authentication::UserInfo, order::OrderInfo},
    models::{NewOrder, Order, OrderRest, OrderStatus, StructureWithElements, UpdateOrder},
    roles::RangerRole,
    services::database::order::{
        CreateOrder, GetCustomElementsByOrder, GetEnvironmentsByOrder, GetPlotsByOrder,
        GetStructuresByOrder, GetTrainingObjectivesByOrder,
    },
    utilities::{create_database_error_handler, create_mailbox_error_handler},
    AppState,
};
use actix_web::{
    get, post, put,
    web::{Data, Json},
};
use anyhow::Result;

#[post("")]
pub async fn create_order(
    app_state: Data<AppState>,
    new_order: Json<NewOrder>,
) -> Result<Json<Order>, RangerError> {
    let order = app_state
        .database_address
        .send(CreateOrder(new_order.into_inner()))
        .await
        .map_err(create_mailbox_error_handler("Database for orders"))?
        .map_err(create_database_error_handler("Create order"))?;

    Ok(Json(order))
}

#[get("")]
pub async fn get_order(
    order: OrderInfo,
    app_state: Data<AppState>,
) -> Result<Json<OrderRest>, RangerError> {
    let order = order.into_inner();

    let training_objectives = app_state
        .database_address
        .send(GetTrainingObjectivesByOrder(order.clone()))
        .await
        .map_err(create_mailbox_error_handler(
            "Database for training objectives",
        ))?
        .map_err(create_database_error_handler("Get training objectives"))?;
    let structures: StructureWithElements = app_state
        .database_address
        .send(GetStructuresByOrder(order.clone()))
        .await
        .map_err(create_mailbox_error_handler("Database for structures"))?
        .map_err(create_database_error_handler("Get structures"))?;
    let environments = app_state
        .database_address
        .send(GetEnvironmentsByOrder(order.clone()))
        .await
        .map_err(create_mailbox_error_handler("Database for environments"))?
        .map_err(create_database_error_handler("Get environments"))?;
    let custom_elements = app_state
        .database_address
        .send(GetCustomElementsByOrder(order.clone()))
        .await
        .map_err(create_mailbox_error_handler("Database for custom elements"))?
        .map_err(create_database_error_handler("Get custom elements"))?;
    let plots = app_state
        .database_address
        .send(GetPlotsByOrder(order.clone()))
        .await
        .map_err(create_mailbox_error_handler("Database for plots"))?
        .map_err(create_database_error_handler("Get plots"))?;

    Ok(Json(OrderRest::from((
        order,
        training_objectives,
        structures,
        environments,
        custom_elements,
        plots,
    ))))
}

#[put("")]
pub async fn update_order(
    order: OrderInfo,
    update_order: Json<UpdateOrder>,
    user_details: UserInfo,
    app_state: Data<AppState>,
) -> Result<Json<OrderRest>, RangerError> {
    let order = order.into_inner();
    let update_order = update_order.into_inner();

    if user_details.role == RangerRole::Client
        && update_order.status != OrderStatus::Draft
        && update_order.status != OrderStatus::Review
    {
        return Err(RangerError::NotAuthorized);
    }

    let updated_order = app_state
        .database_address
        .send(crate::services::database::order::UpdateOrder(
            order.id,
            update_order.clone(),
        ))
        .await
        .map_err(create_mailbox_error_handler(
            "Database for training objectives",
        ))?
        .map_err(create_database_error_handler("Get training objectives"))?;

    let training_objectives = app_state
        .database_address
        .send(GetTrainingObjectivesByOrder(order.clone()))
        .await
        .map_err(create_mailbox_error_handler(
            "Database for training objectives",
        ))?
        .map_err(create_database_error_handler("Get training objectives"))?;
    let structures: StructureWithElements = app_state
        .database_address
        .send(GetStructuresByOrder(order.clone()))
        .await
        .map_err(create_mailbox_error_handler("Database for structures"))?
        .map_err(create_database_error_handler("Get structures"))?;
    let environments = app_state
        .database_address
        .send(GetEnvironmentsByOrder(order.clone()))
        .await
        .map_err(create_mailbox_error_handler("Database for environments"))?
        .map_err(create_database_error_handler("Get environments"))?;
    let custom_elements = app_state
        .database_address
        .send(GetCustomElementsByOrder(order.clone()))
        .await
        .map_err(create_mailbox_error_handler("Database for custom elements"))?
        .map_err(create_database_error_handler("Get custom elements"))?;
    let plots = app_state
        .database_address
        .send(GetPlotsByOrder(order.clone()))
        .await
        .map_err(create_mailbox_error_handler("Database for plots"))?
        .map_err(create_database_error_handler("Get plots"))?;

    Ok(Json(OrderRest::from((
        updated_order,
        training_objectives,
        structures,
        environments,
        custom_elements,
        plots,
    ))))
}
