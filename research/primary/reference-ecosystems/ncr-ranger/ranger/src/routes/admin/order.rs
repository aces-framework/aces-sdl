use crate::{
    errors::RangerError,
    middleware::order::OrderInfo,
    models::{Order, OrderRest, OrderStatus, StructureWithElements},
    services::database::order::{
        GetCustomElementsByOrder, GetEnvironmentsByOrder, GetOrders, GetPlotsByOrder,
        GetStructuresByOrder, GetTrainingObjectivesByOrder,
    },
    utilities::{create_database_error_handler, create_mailbox_error_handler},
    AppState,
};
use actix_web::{
    get,
    web::{Data, Json},
};
use anyhow::Result;

#[get("")]
pub async fn get_orders_admin(app_state: Data<AppState>) -> Result<Json<Vec<Order>>, RangerError> {
    let orders = app_state
        .database_address
        .send(GetOrders)
        .await
        .map_err(create_mailbox_error_handler("Database for orders"))?
        .map_err(create_database_error_handler("Get orders"))?;

    let filtered_orders = orders
        .into_iter()
        .filter(|order| order.status != OrderStatus::Draft)
        .collect();

    Ok(Json(filtered_orders))
}

#[get("")]
pub async fn get_order_admin(
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
