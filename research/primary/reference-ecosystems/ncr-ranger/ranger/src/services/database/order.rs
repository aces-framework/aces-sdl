use std::collections::HashMap;

use super::Database;
use crate::{
    constants::RECORD_NOT_FOUND,
    models::{
        helpers::uuid::Uuid, CustomElement, CustomElementRest, Environment, EnvironmentElements,
        EnvironmentRest, EnvironmentStrength, EnvironmentWeakness, NewOrder, Order, Plot,
        PlotPoint, PlotPointStructure, PlotRest, PlotWithElements, Skill, SkillRest, StrengthRest,
        Structure, StructureObjective, StructureObjectiveRest, StructureRest,
        StructureWithElements, Threat, ThreatRest, TrainingObjective, TrainingObjectiveRest,
        Weakness, WeaknessRest,
    },
};
use actix::{Handler, Message, ResponseActFuture, WrapFuture};
use actix_web::web::block;
use anyhow::{anyhow, Ok, Result};
use diesel::RunQueryDsl;

#[derive(Message)]
#[rtype(result = "Result<Order>")]
pub struct CreateOrder(pub NewOrder);

impl Handler<CreateOrder> for Database {
    type Result = ResponseActFuture<Self, Result<Order>>;

    fn handle(&mut self, msg: CreateOrder, _ctx: &mut Self::Context) -> Self::Result {
        let new_order = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let order = block(move || {
                    new_order.create_insert().execute(&mut connection)?;
                    let order = Order::by_id(new_order.id).first(&mut connection)?;

                    Ok(order)
                })
                .await??;

                Ok(order)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Order>")]
pub struct GetOrder(pub Uuid);

impl Handler<GetOrder> for Database {
    type Result = ResponseActFuture<Self, Result<Order>>;

    fn handle(&mut self, msg: GetOrder, _ctx: &mut Self::Context) -> Self::Result {
        let uuid = msg.0;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let order = block(move || {
                    let order = Order::by_id(uuid).first(&mut connection)?;

                    Ok(order)
                })
                .await??;

                Ok(order)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Order>")]
pub struct UpdateOrder(pub Uuid, pub crate::models::UpdateOrder);

impl Handler<UpdateOrder> for Database {
    type Result = ResponseActFuture<Self, Result<Order>>;

    fn handle(&mut self, msg: UpdateOrder, _ctx: &mut Self::Context) -> Self::Result {
        let UpdateOrder(uuid, update_order) = msg;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let order = block(move || {
                    let updated_rows = update_order.create_update(uuid).execute(&mut connection)?;
                    if updated_rows != 1 {
                        return Err(anyhow!(RECORD_NOT_FOUND));
                    }

                    Ok(Order::by_id(uuid).first(&mut connection)?)
                })
                .await??;

                Ok(order)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Vec<Order>>")]
pub struct GetOrders;

impl Handler<GetOrders> for Database {
    type Result = ResponseActFuture<Self, Result<Vec<Order>>>;

    fn handle(&mut self, _: GetOrders, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let order = block(move || {
                    let orders = Order::all().load(&mut connection)?;

                    Ok(orders)
                })
                .await??;

                Ok(order)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct UpsertTrainingObjective(pub Uuid, pub Option<Uuid>, pub TrainingObjectiveRest);

impl Handler<UpsertTrainingObjective> for Database {
    type Result = ResponseActFuture<Self, Result<()>>;

    fn handle(&mut self, msg: UpsertTrainingObjective, _ctx: &mut Self::Context) -> Self::Result {
        let UpsertTrainingObjective(
            order_uuid,
            existing_training_objective_uuid,
            training_objective_rest,
        ) = msg;
        let training_objective =
            TrainingObjective::new(order_uuid, training_objective_rest.objective.clone());
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                block(move || {
                    if let Some(existing_training_objective_uuid) = existing_training_objective_uuid
                    {
                        TrainingObjective::hard_delete_by_id(existing_training_objective_uuid)
                            .execute(&mut connection)?;
                    }
                    training_objective
                        .create_insert()
                        .execute(&mut connection)?;
                    let threats = training_objective_rest
                        .threats
                        .into_iter()
                        .map(|threat| Threat::new(training_objective.id, threat.threat))
                        .collect::<Vec<Threat>>();
                    Threat::batch_insert(threats).execute(&mut connection)?;

                    Ok(())
                })
                .await??;

                Ok(())
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct UpsertEnvironment(pub Uuid, pub Option<Uuid>, pub EnvironmentRest);

impl Handler<UpsertEnvironment> for Database {
    type Result = ResponseActFuture<Self, Result<()>>;

    fn handle(&mut self, msg: UpsertEnvironment, _ctx: &mut Self::Context) -> Self::Result {
        let UpsertEnvironment(order_uuid, existing_environment_uuid, environment_rest) = msg;
        let environment = Environment::new(order_uuid, environment_rest.clone());
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                block(move || {
                    if let Some(existing_environment_uuid) = existing_environment_uuid {
                        Environment::hard_delete_by_id(existing_environment_uuid)
                            .execute(&mut connection)?;
                    }
                    environment.create_insert().execute(&mut connection)?;
                    if let Some(weaknesses) = environment_rest.weaknesses {
                        let weaknesses = weaknesses
                            .into_iter()
                            .map(|weakness| EnvironmentWeakness::new(environment.id, weakness))
                            .collect::<Vec<EnvironmentWeakness>>();
                        EnvironmentWeakness::batch_insert(weaknesses).execute(&mut connection)?;
                    }
                    if let Some(strengths) = environment_rest.strengths {
                        let strengths = strengths
                            .into_iter()
                            .map(|strength| EnvironmentStrength::new(environment.id, strength))
                            .collect::<Vec<EnvironmentStrength>>();
                        EnvironmentStrength::batch_insert(strengths).execute(&mut connection)?;
                    }

                    Ok(())
                })
                .await??;

                Ok(())
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct DeleteEnvironment(pub Uuid);

impl Handler<DeleteEnvironment> for Database {
    type Result = ResponseActFuture<Self, Result<()>>;

    fn handle(&mut self, msg: DeleteEnvironment, _ctx: &mut Self::Context) -> Self::Result {
        let DeleteEnvironment(environment_uuid) = msg;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                block(move || {
                    let environment =
                        Environment::by_id(environment_uuid).first(&mut connection)?;
                    environment.hard_delete().execute(&mut connection)?;

                    Ok(())
                })
                .await??;

                Ok(())
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<EnvironmentElements>")]
pub struct GetEnvironmentsByOrder(pub Order);

impl Handler<GetEnvironmentsByOrder> for Database {
    type Result = ResponseActFuture<Self, Result<EnvironmentElements>>;

    fn handle(&mut self, msg: GetEnvironmentsByOrder, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_connection();
        let GetEnvironmentsByOrder(order) = msg;

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let objectives = block(move || {
                    let environments = Environment::by_order(&order).load(&mut connection)?;

                    let mut elements_by_environment: EnvironmentElements = HashMap::new();
                    for environment in &environments {
                        let strengths = EnvironmentStrength::by_environment(environment)
                            .load(&mut connection)?
                            .into_iter()
                            .map(|skill| skill.into())
                            .collect::<Vec<StrengthRest>>();
                        let weaknesses = EnvironmentWeakness::by_environment(environment)
                            .load(&mut connection)?
                            .into_iter()
                            .map(|weakness| weakness.into())
                            .collect::<Vec<WeaknessRest>>();
                        elements_by_environment
                            .insert(environment.clone(), (weaknesses, strengths));
                    }

                    Ok(elements_by_environment)
                })
                .await??;

                Ok(objectives)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct UpsertCustomElement(pub Uuid, pub Option<Uuid>, pub CustomElementRest);

impl Handler<UpsertCustomElement> for Database {
    type Result = ResponseActFuture<Self, Result<()>>;

    fn handle(&mut self, msg: UpsertCustomElement, _ctx: &mut Self::Context) -> Self::Result {
        let UpsertCustomElement(order_uuid, existing_custom_element_uuid, custom_element_rest) =
            msg;
        let custom_element = CustomElement::new(order_uuid, custom_element_rest.clone());
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                block(move || {
                    if let Some(existing_custom_element_uuid) = existing_custom_element_uuid {
                        CustomElement::hard_delete_by_id(existing_custom_element_uuid)
                            .execute(&mut connection)?;
                    }
                    custom_element.create_insert().execute(&mut connection)?;

                    Ok(())
                })
                .await??;

                Ok(())
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct DeleteCustomElement(pub Uuid);

impl Handler<DeleteCustomElement> for Database {
    type Result = ResponseActFuture<Self, Result<()>>;

    fn handle(&mut self, msg: DeleteCustomElement, _ctx: &mut Self::Context) -> Self::Result {
        let DeleteCustomElement(custom_element_id) = msg;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                block(move || {
                    let custom_element =
                        CustomElement::by_id(custom_element_id).first(&mut connection)?;
                    custom_element.hard_delete().execute(&mut connection)?;

                    Ok(())
                })
                .await??;

                Ok(())
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Option<CustomElement>>")]
pub struct GetCustomElement(pub Uuid);

impl Handler<GetCustomElement> for Database {
    type Result = ResponseActFuture<Self, Result<Option<CustomElement>>>;

    fn handle(&mut self, msg: GetCustomElement, _ctx: &mut Self::Context) -> Self::Result {
        let GetCustomElement(custom_element_id) = msg;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let custom_element = block(move || {
                    let custom_element_result =
                        CustomElement::by_id(custom_element_id).first(&mut connection);

                    match custom_element_result {
                        Result::Ok(custom_element) => Ok(Some(custom_element)),
                        Err(diesel::result::Error::NotFound) => Ok(None),
                        Err(err) => Err(err.into()),
                    }
                })
                .await??;

                Ok(custom_element)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<Vec<CustomElement>>")]
pub struct GetCustomElementsByOrder(pub Order);

impl Handler<GetCustomElementsByOrder> for Database {
    type Result = ResponseActFuture<Self, Result<Vec<CustomElement>>>;

    fn handle(&mut self, msg: GetCustomElementsByOrder, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_connection();
        let GetCustomElementsByOrder(order) = msg;

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let objectives = block(move || {
                    let custom_elements = CustomElement::by_order(&order).load(&mut connection)?;

                    Ok(custom_elements)
                })
                .await??;

                Ok(objectives)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<HashMap<TrainingObjective, Vec<ThreatRest>>>")]
pub struct GetTrainingObjectivesByOrder(pub Order);

impl Handler<GetTrainingObjectivesByOrder> for Database {
    type Result = ResponseActFuture<Self, Result<HashMap<TrainingObjective, Vec<ThreatRest>>>>;

    fn handle(
        &mut self,
        get_objectives: GetTrainingObjectivesByOrder,
        _ctx: &mut Self::Context,
    ) -> Self::Result {
        let connection_result = self.get_connection();
        let GetTrainingObjectivesByOrder(order) = get_objectives;

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let objectives = block(move || {
                    let training_objectives =
                        TrainingObjective::by_order(&order).load(&mut connection)?;

                    let mut threats_by_objectives: HashMap<TrainingObjective, Vec<ThreatRest>> =
                        HashMap::new();
                    for trainining_objective in &training_objectives {
                        let threats = Threat::by_objective(trainining_objective)
                            .load(&mut connection)?
                            .into_iter()
                            .map(|threat| threat.into())
                            .collect::<Vec<ThreatRest>>();
                        threats_by_objectives.insert(trainining_objective.clone(), threats);
                    }

                    Ok(threats_by_objectives)
                })
                .await??;

                Ok(objectives)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct DeleteTrainingObjective(pub Uuid);

impl Handler<DeleteTrainingObjective> for Database {
    type Result = ResponseActFuture<Self, Result<()>>;

    fn handle(&mut self, msg: DeleteTrainingObjective, _ctx: &mut Self::Context) -> Self::Result {
        let DeleteTrainingObjective(training_objective_uuid) = msg;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                block(move || {
                    let training_objective =
                        TrainingObjective::by_id(training_objective_uuid).first(&mut connection)?;
                    training_objective.hard_delete().execute(&mut connection)?;

                    Ok(())
                })
                .await??;

                Ok(())
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct UpsertStructure(pub Uuid, pub Option<Uuid>, pub StructureRest);

impl Handler<UpsertStructure> for Database {
    type Result = ResponseActFuture<Self, Result<()>>;

    fn handle(&mut self, msg: UpsertStructure, _ctx: &mut Self::Context) -> Self::Result {
        let UpsertStructure(order_uuid, structure_uuid, new_structure) = msg;
        let new_skills = new_structure.skills.clone();
        let weaknesses = new_structure.weaknesses.clone();
        let training_objectives = new_structure.training_objective_ids.clone();
        let structure = Structure::new(order_uuid, new_structure);
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                block(move || {
                    if let Some(structure_uuid) = structure_uuid {
                        Structure::hard_delete_by_id(structure_uuid).execute(&mut connection)?;
                    }
                    structure.create_insert().execute(&mut connection)?;
                    if let Some(skills) = new_skills {
                        let skills = skills
                            .into_iter()
                            .map(|skill| Skill::new(structure.id, skill))
                            .collect::<Vec<Skill>>();
                        Skill::batch_insert(skills).execute(&mut connection)?;
                    }
                    if let Some(weaknesses) = weaknesses {
                        let weaknesses = weaknesses
                            .into_iter()
                            .map(|weakness| Weakness::new(structure.id, weakness))
                            .collect::<Vec<Weakness>>();
                        Weakness::batch_insert(weaknesses).execute(&mut connection)?;
                    }
                    if let Some(training_objectives) = training_objectives {
                        let training_objectives = training_objectives
                            .into_iter()
                            .map(|training_objective| {
                                StructureObjective::new(structure.id, training_objective)
                            })
                            .collect::<Vec<StructureObjective>>();
                        StructureObjective::batch_insert(training_objectives)
                            .execute(&mut connection)?;
                    }

                    Ok(())
                })
                .await??;

                Ok(())
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<StructureWithElements>")]
pub struct GetStructuresByOrder(pub Order);

impl Handler<GetStructuresByOrder> for Database {
    type Result = ResponseActFuture<Self, Result<StructureWithElements>>;

    fn handle(&mut self, msg: GetStructuresByOrder, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_connection();
        let GetStructuresByOrder(order) = msg;

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let objectives = block(move || {
                    let structures = Structure::by_order(&order).load(&mut connection)?;

                    let mut elements_by_structure: StructureWithElements = HashMap::new();
                    for structure in &structures {
                        let skills = Skill::by_structure(structure)
                            .load(&mut connection)?
                            .into_iter()
                            .map(|skill| skill.into())
                            .collect::<Vec<SkillRest>>();
                        let training_objectives = StructureObjective::by_structure(structure)
                            .load(&mut connection)?
                            .into_iter()
                            .map(|structure_objective| structure_objective.into())
                            .collect::<Vec<StructureObjectiveRest>>();
                        let weaknesses = Weakness::by_structure(structure)
                            .load(&mut connection)?
                            .into_iter()
                            .map(|weakness| weakness.into())
                            .collect::<Vec<WeaknessRest>>();
                        elements_by_structure
                            .insert(structure.clone(), (skills, training_objectives, weaknesses));
                    }

                    Ok(elements_by_structure)
                })
                .await??;

                Ok(objectives)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct DeleteStructure(pub Uuid);

impl Handler<DeleteStructure> for Database {
    type Result = ResponseActFuture<Self, Result<()>>;

    fn handle(&mut self, msg: DeleteStructure, _ctx: &mut Self::Context) -> Self::Result {
        let DeleteStructure(structure_uuid) = msg;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                block(move || {
                    let structure = Structure::by_id(structure_uuid).first(&mut connection)?;
                    structure.hard_delete().execute(&mut connection)?;

                    Ok(())
                })
                .await??;

                Ok(())
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct UpsertPlot(pub Uuid, pub Option<Uuid>, pub PlotRest);

impl Handler<UpsertPlot> for Database {
    type Result = ResponseActFuture<Self, Result<()>>;

    fn handle(&mut self, msg: UpsertPlot, _ctx: &mut Self::Context) -> Self::Result {
        let UpsertPlot(order_uuid, existing_plot_uuid, plot_rest) = msg;
        let plot = Plot::new(order_uuid, plot_rest.clone());
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                block(move || {
                    if let Some(existing_plot_uuid) = existing_plot_uuid {
                        Plot::hard_delete_by_id(existing_plot_uuid).execute(&mut connection)?;
                    }
                    plot.create_insert().execute(&mut connection)?;
                    if let Some(plot_points) = plot_rest.plot_points {
                        let rest_plot_points = plot_points.clone();
                        let plot_points = plot_points
                            .into_iter()
                            .map(|plot_point| PlotPoint::new(plot.id, plot_point))
                            .collect::<Vec<PlotPoint>>();
                        PlotPoint::batch_insert(plot_points).execute(&mut connection)?;
                        for rest_plot_point in &rest_plot_points {
                            if let Some(plot_point_structures) = &rest_plot_point.structure_ids {
                                let plot_point_structures = plot_point_structures
                                    .iter()
                                    .map(|plot_point_structure| {
                                        PlotPointStructure::new(
                                            rest_plot_point.id,
                                            plot_point_structure.clone(),
                                        )
                                    })
                                    .collect::<Vec<PlotPointStructure>>();
                                PlotPointStructure::batch_insert(plot_point_structures)
                                    .execute(&mut connection)?;
                            }
                        }
                    }

                    Ok(())
                })
                .await??;

                Ok(())
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<PlotWithElements>")]
pub struct GetPlotsByOrder(pub Order);

impl Handler<GetPlotsByOrder> for Database {
    type Result = ResponseActFuture<Self, Result<PlotWithElements>>;

    fn handle(&mut self, msg: GetPlotsByOrder, _ctx: &mut Self::Context) -> Self::Result {
        let connection_result = self.get_connection();
        let GetPlotsByOrder(order) = msg;

        Box::pin(
            async move {
                let mut connection = connection_result?;
                let plots = block(move || {
                    let plots = Plot::by_order(&order).load(&mut connection)?;
                    let mut elements_by_plot: PlotWithElements = HashMap::new();
                    for plot in &plots {
                        let plot_points: Vec<PlotPoint> =
                            PlotPoint::by_plot(plot).load(&mut connection)?;
                        let mut elements_by_plot_point: HashMap<
                            PlotPoint,
                            Vec<PlotPointStructure>,
                        > = HashMap::new();
                        for plot_point in &plot_points {
                            let plot_point_structures: Vec<PlotPointStructure> =
                                PlotPointStructure::by_plot_point(plot_point)
                                    .load(&mut connection)?;
                            elements_by_plot_point
                                .insert(plot_point.clone(), plot_point_structures);
                        }

                        elements_by_plot.insert(plot.clone(), elements_by_plot_point);
                    }

                    Ok(elements_by_plot)
                })
                .await??;

                Ok(plots)
            }
            .into_actor(self),
        )
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct DeletePlot(pub Uuid);

impl Handler<DeletePlot> for Database {
    type Result = ResponseActFuture<Self, Result<()>>;

    fn handle(&mut self, msg: DeletePlot, _ctx: &mut Self::Context) -> Self::Result {
        let DeletePlot(plot_uuid) = msg;
        let connection_result = self.get_connection();

        Box::pin(
            async move {
                let mut connection = connection_result?;
                block(move || {
                    let plot = Plot::by_id(plot_uuid).first(&mut connection)?;
                    plot.hard_delete().execute(&mut connection)?;

                    Ok(())
                })
                .await??;

                Ok(())
            }
            .into_actor(self),
        )
    }
}
