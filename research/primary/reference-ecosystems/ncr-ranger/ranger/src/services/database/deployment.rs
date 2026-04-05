use super::Database;
use crate::models::helpers::uuid::Uuid;
use crate::models::{Deployment, DeploymentElement, NewDeployment, ScenarioReference};
use crate::services::websocket::{SocketDeployment, SocketDeploymentElement};
use actix::{Handler, Message, ResponseActFuture, WrapFuture};
use actix_web::web::block;
use anyhow::{anyhow, Ok, Result};
use diesel::RunQueryDsl;
use log::info;

#[derive(Message)]
#[rtype(result = "Result<Deployment>")]
pub struct CreateDeployment(pub NewDeployment);

impl Handler<CreateDeployment> for Database {
    type Result = ResponseActFuture<Self, Result<Deployment>>;

    fn handle(&mut self, msg: CreateDeployment, _ctx: &mut Self::Context) -> Self::Result {
        let new_deployment = msg.0;
        let connection_result = self.get_connection();
        let websocket_manager = self.websocket_manager_address.clone();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let deployment = block(move || {
                    new_deployment.create_insert().execute(&mut connection)?;
                    let deployment = Deployment::by_id(new_deployment.id).first(&mut connection)?;
                    websocket_manager.do_send(SocketDeployment(
                        deployment.exercise_id,
                        (deployment.exercise_id, deployment.id, deployment.clone()).into(),
                    ));
                    Ok(deployment)
                })
                .await??;

                Ok(deployment)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Vec<Deployment>>")]
pub struct GetDeployments(pub Uuid);

impl Handler<GetDeployments> for Database {
    type Result = ResponseActFuture<Self, Result<Vec<Deployment>>>;

    fn handle(&mut self, msg: GetDeployments, _ctx: &mut Self::Context) -> Self::Result {
        let id = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let deployments = block(move || {
                    let deployments = Deployment::by_exercise_id(id).load(&mut connection)?;
                    Ok(deployments)
                })
                .await??;

                Ok(deployments)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Deployment>")]
pub struct GetDeployment(pub Uuid);

impl Handler<GetDeployment> for Database {
    type Result = ResponseActFuture<Self, Result<Deployment>>;

    fn handle(&mut self, msg: GetDeployment, _ctx: &mut Self::Context) -> Self::Result {
        let id = msg.0;
        let connection_result = self.get_shared_connection();

        Box::pin(
            async move {
                let deployment = block(move || {
                    let mutex_connection = connection_result?;
                    let mut connection = mutex_connection
                        .lock()
                        .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;
                    let deployment = Deployment::by_id(id).first(&mut *connection)?;
                    Ok(deployment)
                })
                .await??;

                Ok(deployment)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Uuid>")]
pub struct DeleteDeployment(pub Uuid, pub bool);

impl Handler<DeleteDeployment> for Database {
    type Result = ResponseActFuture<Self, Result<Uuid>>;

    fn handle(&mut self, msg: DeleteDeployment, _ctx: &mut Self::Context) -> Self::Result {
        let DeleteDeployment(id, use_shared_connection) = msg;
        let connection_result = self.pick_connection(use_shared_connection);

        Box::pin(
            async move {
                let id = block(move || {
                    let mutex_connection = connection_result?;
                    let mut connection = mutex_connection
                        .lock()
                        .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;
                    let deployment = Deployment::by_id(id).first(&mut *connection)?;
                    deployment
                        .soft_delete_elements()
                        .execute(&mut *connection)?;
                    deployment.soft_delete().execute(&mut *connection)?;

                    info!("Deployment {:?} deleted", id.0);
                    Ok(id)
                })
                .await??;

                Ok(id)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<DeploymentElement>")]
pub struct CreateDeploymentElement(pub Uuid, pub DeploymentElement, pub bool);

impl Handler<CreateDeploymentElement> for Database {
    type Result = ResponseActFuture<Self, Result<DeploymentElement>>;

    fn handle(&mut self, msg: CreateDeploymentElement, _ctx: &mut Self::Context) -> Self::Result {
        let CreateDeploymentElement(exercise_uuid, new_deployment_element, use_shared_connection) =
            msg;
        let websocket_manager = self.websocket_manager_address.clone();
        let connection_result = self.pick_connection(use_shared_connection);
        Box::pin(
            async move {
                let deployment_element = block(move || {
                    let mutex_connection = connection_result?;
                    let mut connection = mutex_connection
                        .lock()
                        .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;
                    new_deployment_element
                        .create_insert()
                        .execute(&mut *connection)?;
                    let deployment_element = DeploymentElement::by_id(new_deployment_element.id)
                        .first(&mut *connection)?;
                    websocket_manager.do_send(SocketDeploymentElement(
                        exercise_uuid,
                        (
                            exercise_uuid,
                            deployment_element.id,
                            deployment_element.clone(),
                            false,
                        )
                            .into(),
                    ));

                    Ok(deployment_element)
                })
                .await??;

                Ok(deployment_element)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<DeploymentElement>")]
pub struct CreateOrIgnoreDeploymentElement(pub Uuid, pub DeploymentElement, pub bool);

impl Handler<CreateOrIgnoreDeploymentElement> for Database {
    type Result = ResponseActFuture<Self, Result<DeploymentElement>>;

    fn handle(
        &mut self,
        msg: CreateOrIgnoreDeploymentElement,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let CreateOrIgnoreDeploymentElement(
            exercise_uuid,
            new_deployment_element,
            use_shared_connection,
        ) = msg;
        let connection_result = self.pick_connection(use_shared_connection);
        let websocket_manager = self.websocket_manager_address.clone();

        Box::pin(
            async move {
                let deployment_element = block(move || {
                    let mutex_connection = connection_result?;
                    let mut connection = mutex_connection
                        .lock()
                        .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;
                    new_deployment_element
                        .create_insert_or_ignore()
                        .execute(&mut *connection)?;

                    let deployment_element =
                        DeploymentElement::by_deployment_id_by_scenario_reference(
                            new_deployment_element.deployment_id,
                            new_deployment_element.scenario_reference,
                        )
                        .first(&mut *connection)?;

                    websocket_manager.do_send(SocketDeploymentElement(
                        exercise_uuid,
                        (
                            exercise_uuid,
                            deployment_element.id,
                            deployment_element.clone(),
                            false,
                        )
                            .into(),
                    ));

                    Ok(deployment_element)
                })
                .await??;

                Ok(deployment_element)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<DeploymentElement>")]
pub struct UpdateDeploymentElement(pub Uuid, pub DeploymentElement, pub bool);

impl Handler<UpdateDeploymentElement> for Database {
    type Result = ResponseActFuture<Self, Result<DeploymentElement>>;

    fn handle(&mut self, msg: UpdateDeploymentElement, _ctx: &mut Self::Context) -> Self::Result {
        let UpdateDeploymentElement(exercise_uuid, new_deployment_element, use_shared_connection) =
            msg;
        let websocket_manager = self.websocket_manager_address.clone();
        let connection_result = self.pick_connection(use_shared_connection);

        Box::pin(
            async move {
                let deployment_element = block(move || {
                    let mutex_connection = connection_result?;
                    let mut connection = mutex_connection
                        .lock()
                        .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;
                    let updated_rows = new_deployment_element
                        .create_update()
                        .execute(&mut *connection)?;
                    if updated_rows != 1 {
                        return Err(anyhow::anyhow!("Deployment element not found"));
                    }
                    websocket_manager.do_send(SocketDeploymentElement(
                        exercise_uuid,
                        (
                            exercise_uuid,
                            new_deployment_element.id,
                            new_deployment_element.clone(),
                            true,
                        )
                            .into(),
                    ));

                    Ok(DeploymentElement::by_id(new_deployment_element.id)
                        .first(&mut *connection)?)
                })
                .await??;

                Ok(deployment_element)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<DeploymentElement>")]
pub struct GetDeploymentElementByDeploymentIdByScenarioReference(
    pub Uuid,
    pub Box<dyn ScenarioReference>,
    pub bool,
);

impl Handler<GetDeploymentElementByDeploymentIdByScenarioReference> for Database {
    type Result = ResponseActFuture<Self, Result<DeploymentElement>>;

    fn handle(
        &mut self,
        msg: GetDeploymentElementByDeploymentIdByScenarioReference,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let GetDeploymentElementByDeploymentIdByScenarioReference(
            deployment_id,
            scenario_reference,
            use_shared_connection,
        ) = msg;
        let connection_result = self.pick_connection(use_shared_connection);

        Box::pin(
            async move {
                let deployment_element = block(move || {
                    let mutex_connection = connection_result?;
                    let mut connection = mutex_connection
                        .lock()
                        .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;
                    let deployment_element =
                        DeploymentElement::by_deployment_id_by_scenario_reference(
                            deployment_id,
                            scenario_reference.reference(),
                        )
                        .first(&mut *connection)?;
                    Ok(deployment_element)
                })
                .await??;

                Ok(deployment_element)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Vec<DeploymentElement>>")]
pub struct GetDeploymentElementByDeploymentId(pub Uuid, pub bool);

impl Handler<GetDeploymentElementByDeploymentId> for Database {
    type Result = ResponseActFuture<Self, Result<Vec<DeploymentElement>>>;

    fn handle(
        &mut self,
        msg: GetDeploymentElementByDeploymentId,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let GetDeploymentElementByDeploymentId(deployment_id, use_shared_connection) = msg;
        let connection_result = self.pick_connection(use_shared_connection);

        Box::pin(
            async move {
                let deployment_elements = block(move || {
                    let mutex_connection = connection_result?;
                    let mut connection = mutex_connection
                        .lock()
                        .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;
                    let deployment_elements = DeploymentElement::by_deployment_id(deployment_id)
                        .load(&mut *connection)?;

                    Ok(deployment_elements)
                })
                .await??;

                Ok(deployment_elements)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<DeploymentElement>")]
pub struct GetDeploymentElementByDeploymentIdByHandlerReference(pub Uuid, pub String);

impl Handler<GetDeploymentElementByDeploymentIdByHandlerReference> for Database {
    type Result = ResponseActFuture<Self, Result<DeploymentElement>>;

    fn handle(
        &mut self,
        msg: GetDeploymentElementByDeploymentIdByHandlerReference,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let deployment_id = msg.0;
        let handler_reference = msg.1.reference();
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let deployment_element = block(move || {
                    DeploymentElement::by_deployment_id_by_handler_reference(
                        deployment_id,
                        handler_reference,
                    )
                    .first(&mut connection)
                })
                .await??;

                Ok(deployment_element)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Vec<DeploymentElement>>")]
pub struct GetDeploymentElementByEventId(pub Uuid, pub bool);

impl Handler<GetDeploymentElementByEventId> for Database {
    type Result = ResponseActFuture<Self, Result<Vec<DeploymentElement>>>;

    fn handle(
        &mut self,
        msg: GetDeploymentElementByEventId,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let GetDeploymentElementByEventId(event_id, use_shared_connection) = msg;
        let connection_result = self.pick_connection(use_shared_connection);

        Box::pin(
            async move {
                let deployment_elements = block(move || {
                    let mutex_connection = connection_result?;
                    let mut connection = mutex_connection
                        .lock()
                        .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;
                    let deployment_elements =
                        DeploymentElement::by_event_id(event_id).load(&mut *connection)?;

                    Ok(deployment_elements)
                })
                .await??;

                Ok(deployment_elements)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Vec<DeploymentElement>>")]
pub struct GetDeploymentElementByEventIdByParentNodeId(pub Uuid, pub Uuid, pub bool);

impl Handler<GetDeploymentElementByEventIdByParentNodeId> for Database {
    type Result = ResponseActFuture<Self, Result<Vec<DeploymentElement>>>;

    fn handle(
        &mut self,
        msg: GetDeploymentElementByEventIdByParentNodeId,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let GetDeploymentElementByEventIdByParentNodeId(
            event_id,
            handler_reference,
            use_shared_connection,
        ) = msg;
        let connection_result = self.pick_connection(use_shared_connection);

        Box::pin(
            async move {
                let deployment_elements = block(move || {
                    let mutex_connection = connection_result?;
                    let mut connection = mutex_connection
                        .lock()
                        .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;
                    let deployment_elements = DeploymentElement::by_event_id_by_parent_node_id(
                        event_id,
                        handler_reference,
                    )
                    .load(&mut *connection)?;

                    Ok(deployment_elements)
                })
                .await??;

                Ok(deployment_elements)
            }
            .into_actor(self),
        )
    }
}
