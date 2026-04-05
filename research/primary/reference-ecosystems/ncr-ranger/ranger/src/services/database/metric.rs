use super::Database;
use crate::constants::RECORD_NOT_FOUND;
use crate::models::metric::Metric;
use crate::models::Score;
use crate::models::{helpers::uuid::Uuid, metric::NewMetric};
use crate::services::websocket::SocketScoring;
use actix::{Handler, Message, ResponseActFuture, WrapFuture};
use actix_web::web::block;
use anyhow::{anyhow, Ok, Result};
use diesel::RunQueryDsl;

#[derive(Message)]
#[rtype(result = "Result<Metric>")]
pub struct CreateMetric(pub NewMetric);

impl Handler<CreateMetric> for Database {
    type Result = ResponseActFuture<Self, Result<Metric>>;

    fn handle(&mut self, msg: CreateMetric, _ctx: &mut Self::Context) -> Self::Result {
        let new_manual_metric = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let manual_metric = block(move || {
                    new_manual_metric.create_insert().execute(&mut connection)?;
                    let manual_metric =
                        Metric::by_id(new_manual_metric.id).first(&mut connection)?;

                    Ok(manual_metric)
                })
                .await??;

                Ok(manual_metric)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Metric>")]
pub struct UpdateMetric(pub Uuid, pub crate::models::UpdateMetric);

impl Handler<UpdateMetric> for Database {
    type Result = ResponseActFuture<Self, Result<Metric>>;

    fn handle(&mut self, msg: UpdateMetric, _ctx: &mut Self::Context) -> Self::Result {
        let UpdateMetric(uuid, update_manual_metric) = msg;
        let connection_result = self.get_connection();
        let websocket_manager = self.websocket_manager_address.clone();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let metric = block(move || {
                    let updated_rows = update_manual_metric
                        .create_update(uuid)
                        .execute(&mut connection)?;
                    if updated_rows != 1 {
                        return Err(anyhow!(RECORD_NOT_FOUND));
                    }
                    let metric = Metric::by_id(uuid).first(&mut connection)?;
                    if metric.score.is_some() {
                        let score: Score = metric.clone().into();

                        let scoring_msg = SocketScoring(
                            score.exercise_id,
                            (score.id, score.exercise_id, score).into(),
                        );
                        websocket_manager.do_send(scoring_msg);
                    }
                    Ok(metric)
                })
                .await??;

                Ok(metric)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Metric>")]
pub struct GetMetric(pub Uuid);

impl Handler<GetMetric> for Database {
    type Result = ResponseActFuture<Self, Result<Metric>>;

    fn handle(&mut self, msg: GetMetric, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_connection();
        let deployment_uuid = msg.0;

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let manual_metric = block(move || {
                    let manual_metric = Metric::by_id(deployment_uuid).first(&mut connection)?;

                    Ok(manual_metric)
                })
                .await??;

                Ok(manual_metric)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Vec<Metric>>")]
pub struct GetMetrics(pub Uuid);

impl Handler<GetMetrics> for Database {
    type Result = ResponseActFuture<Self, Result<Vec<Metric>>>;

    fn handle(&mut self, msg: GetMetrics, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_connection();
        let deployment_uuid = msg.0;

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let manual_metric = block(move || {
                    let manual_metric =
                        Metric::by_deployment_id(deployment_uuid).load(&mut connection)?;

                    Ok(manual_metric)
                })
                .await??;

                Ok(manual_metric)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Uuid>")]
pub struct DeleteMetric(pub Uuid, pub bool);
impl Handler<DeleteMetric> for Database {
    type Result = ResponseActFuture<Self, Result<Uuid>>;

    fn handle(&mut self, msg: DeleteMetric, _ctx: &mut Self::Context) -> Self::Result {
        let DeleteMetric(id, use_shared_connection) = msg;
        let connection_result = self.pick_connection(use_shared_connection);

        Box::pin(
            async move {
                let id = block(move || {
                    let mutex_connection = connection_result?;
                    let mut connection = mutex_connection
                        .lock()
                        .map_err(|error| anyhow!("Error locking Mutex connection: {:?}", error))?;
                    let manual_metric = Metric::by_id(id).first(&mut *connection)?;
                    manual_metric.soft_delete().execute(&mut *connection)?;

                    Ok(id)
                })
                .await??;

                Ok(id)
            }
            .into_actor(self),
        )
    }
}
