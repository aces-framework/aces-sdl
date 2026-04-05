use super::helpers::uuid::Uuid;
use crate::{
    constants::{MAX_ORDER_NAME_LENGTH, NAIVEDATETIME_DEFAULT_VALUE},
    errors::RangerError,
    schema::{
        custom_elements, environment_strength, environment_weakness, environments, orders,
        plot_point_structures, plot_points, plots, skills, structure_training_objectives,
        structure_weaknesses, structures, threats, training_objectives,
    },
    services::database::{
        All, Create, DeleteById, FilterExisting, SelectById, SelectByIdFromAll,
        SelectByIdFromAllReference, UpdateById,
    },
    utilities::Validation,
};
use chrono::NaiveDateTime;
use diesel::{
    associations::{Associations, Identifiable},
    deserialize::FromSqlRow,
    expression::AsExpression,
    insert_into,
    prelude::{Insertable, Queryable},
    sql_types::Text,
    AsChangeset, BelongingToDsl, ExpressionMethods, QueryDsl, Selectable, SelectableHelper,
};
use serde::{Deserialize, Serialize};
use std::{collections::HashMap, hash::Hash, result::Result as StdResult};

#[derive(
    Clone, Copy, Debug, PartialEq, FromSqlRow, AsExpression, Eq, Deserialize, Serialize, Default,
)]
#[diesel(sql_type = Text)]
#[serde(rename_all = "camelCase")]
pub enum OrderStatus {
    #[default]
    Draft,
    Review,
    InProgress,
    Ready,
    Finished,
}

#[derive(Insertable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = orders)]
pub struct NewOrder {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub name: String,
    pub client_id: String,
    #[serde(default)]
    pub status: OrderStatus,
}

impl NewOrder {
    pub fn create_insert(&self) -> Create<&Self, orders::table> {
        insert_into(orders::table).values(self)
    }
}

impl Validation for NewOrder {
    fn validate(&self) -> StdResult<(), RangerError> {
        if self.name.len() > MAX_ORDER_NAME_LENGTH {
            return Err(RangerError::OrderNameTooLong);
        }
        Ok(())
    }
}

#[derive(
    AsChangeset, Queryable, Selectable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize,
)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = orders)]
pub struct UpdateOrder {
    pub status: OrderStatus,
}

impl UpdateOrder {
    pub fn create_update(
        &self,
        id: Uuid,
    ) -> UpdateById<orders::id, orders::deleted_at, orders::table, &Self> {
        diesel::update(orders::table)
            .filter(orders::id.eq(id))
            .filter(orders::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
            .set(self)
    }
}

#[derive(
    Identifiable, Queryable, Selectable, Debug, PartialEq, Eq, Clone, Serialize, Deserialize,
)]
#[serde(rename_all = "camelCase")]
#[diesel(table_name = orders)]
pub struct Order {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub name: String,
    pub client_id: String,
    pub status: OrderStatus,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
}

impl Order {
    fn all_with_deleted() -> All<orders::table, Self> {
        orders::table.select(Self::as_select())
    }

    pub fn all() -> FilterExisting<All<orders::table, Self>, orders::deleted_at> {
        Self::all_with_deleted().filter(orders::deleted_at.eq(*NAIVEDATETIME_DEFAULT_VALUE))
    }

    pub fn by_id(id: Uuid) -> SelectById<orders::table, orders::id, orders::deleted_at, Self> {
        Self::all().filter(orders::id.eq(id))
    }

    pub fn is_owner(&self, client_id: &str) -> bool {
        self.client_id == client_id
    }
}

#[derive(
    Insertable, Identifiable, Queryable, Selectable, Debug, PartialEq, Associations, Eq, Clone, Hash,
)]
#[diesel(belongs_to(Order, foreign_key = order_id))]
#[diesel(table_name = training_objectives)]
pub struct TrainingObjective {
    pub id: Uuid,
    pub order_id: Uuid,
    pub objective: String,
}

impl TrainingObjective {
    pub fn new(order_id: Uuid, objective: String) -> Self {
        Self {
            id: Uuid::random(),
            order_id,
            objective,
        }
    }

    pub fn create_insert(&self) -> Create<&Self, training_objectives::table> {
        insert_into(training_objectives::table).values(self)
    }

    pub fn hard_delete_by_id(
        id: Uuid,
    ) -> DeleteById<training_objectives::id, training_objectives::table> {
        diesel::delete(training_objectives::table.filter(training_objectives::id.eq(id)))
    }

    pub fn hard_delete(&self) -> DeleteById<training_objectives::id, training_objectives::table> {
        Self::hard_delete_by_id(self.id)
    }

    fn all() -> All<training_objectives::table, Self> {
        training_objectives::table.select(Self::as_select())
    }

    pub fn by_id(
        id: Uuid,
    ) -> SelectByIdFromAll<training_objectives::table, training_objectives::id, Self> {
        Self::all().filter(training_objectives::id.eq(id))
    }

    pub fn by_order(
        order: &Order,
    ) -> SelectByIdFromAllReference<training_objectives::table, training_objectives::order_id, Self>
    {
        Self::belonging_to(order).select(Self::as_select())
    }
}

#[derive(
    Insertable,
    Identifiable,
    Associations,
    Queryable,
    Selectable,
    Debug,
    PartialEq,
    Eq,
    Clone,
    Serialize,
    Deserialize,
)]
#[serde(rename_all = "camelCase")]
#[diesel(belongs_to(TrainingObjective, foreign_key = training_objective_id))]
#[diesel(table_name = threats)]
pub struct Threat {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub training_objective_id: Uuid,
    pub threat: String,
}

impl Threat {
    pub fn new(training_objective_id: Uuid, threat: String) -> Self {
        Self {
            id: Uuid::random(),
            training_objective_id,
            threat,
        }
    }

    pub fn by_objective(
        objective: &TrainingObjective,
    ) -> SelectByIdFromAllReference<threats::table, threats::training_objective_id, Self> {
        Self::belonging_to(objective).select(Self::as_select())
    }

    pub fn batch_insert(threats: Vec<Self>) -> Create<Vec<Self>, threats::table> {
        insert_into(threats::table).values(threats)
    }
}

#[derive(
    Insertable, Identifiable, Queryable, Selectable, Debug, PartialEq, Associations, Eq, Clone, Hash,
)]
#[diesel(belongs_to(Order, foreign_key = order_id))]
#[diesel(table_name = structures)]
pub struct Structure {
    pub id: Uuid,
    pub order_id: Uuid,
    pub parent_id: Option<Uuid>,
    pub name: String,
    pub description: Option<String>,
}

impl Structure {
    pub fn new(order_id: Uuid, new_structure: StructureRest) -> Self {
        Self {
            id: new_structure.id,
            order_id,
            name: new_structure.name,
            description: new_structure.description,
            parent_id: new_structure.parent_id,
        }
    }

    pub fn create_insert(&self) -> Create<&Self, structures::table> {
        insert_into(structures::table).values(self)
    }

    pub fn hard_delete_by_id(id: Uuid) -> DeleteById<structures::id, structures::table> {
        diesel::delete(structures::table.filter(structures::id.eq(id)))
    }

    pub fn hard_delete(&self) -> DeleteById<structures::id, structures::table> {
        Self::hard_delete_by_id(self.id)
    }

    fn all() -> All<structures::table, Self> {
        structures::table.select(Self::as_select())
    }

    pub fn by_id(id: Uuid) -> SelectByIdFromAll<structures::table, structures::id, Self> {
        Self::all().filter(structures::id.eq(id))
    }

    pub fn by_order(
        order: &Order,
    ) -> SelectByIdFromAllReference<structures::table, structures::order_id, Self> {
        Self::belonging_to(order).select(Self::as_select())
    }
}

#[derive(
    Insertable,
    Identifiable,
    Associations,
    Queryable,
    Selectable,
    Debug,
    PartialEq,
    Eq,
    Clone,
    Serialize,
    Deserialize,
)]
#[serde(rename_all = "camelCase")]
#[diesel(belongs_to(Structure, foreign_key = structure_id))]
#[diesel(table_name = skills)]
pub struct Skill {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub structure_id: Uuid,
    pub skill: String,
}

impl Skill {
    pub fn new(structure_id: Uuid, skill: SkillRest) -> Self {
        Self {
            id: skill.id,
            structure_id,
            skill: skill.skill,
        }
    }

    pub fn by_structure(
        structure: &Structure,
    ) -> SelectByIdFromAllReference<skills::table, skills::structure_id, Self> {
        Self::belonging_to(structure).select(Self::as_select())
    }

    pub fn batch_insert(skills: Vec<Self>) -> Create<Vec<Self>, skills::table> {
        insert_into(skills::table).values(skills)
    }
}

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SkillRest {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub skill: String,
}

impl From<Skill> for SkillRest {
    fn from(skill: Skill) -> Self {
        Self {
            id: skill.id,
            skill: skill.skill,
        }
    }
}

#[derive(
    Insertable,
    Identifiable,
    Associations,
    Queryable,
    Selectable,
    Debug,
    PartialEq,
    Eq,
    Clone,
    Serialize,
    Deserialize,
)]
#[serde(rename_all = "camelCase")]
#[diesel(belongs_to(Structure, foreign_key = structure_id))]
#[diesel(table_name = structure_training_objectives)]
pub struct StructureObjective {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub structure_id: Uuid,
    pub training_objective_id: Uuid,
}

impl StructureObjective {
    pub fn new(structure_id: Uuid, structure_objective: StructureObjectiveRest) -> Self {
        Self {
            id: structure_objective.id,
            structure_id,
            training_objective_id: structure_objective.training_objective_id,
        }
    }

    pub fn by_structure(
        structure: &Structure,
    ) -> SelectByIdFromAllReference<
        structure_training_objectives::table,
        structure_training_objectives::structure_id,
        Self,
    > {
        Self::belonging_to(structure).select(Self::as_select())
    }

    pub fn batch_insert(
        training_objective_ids: Vec<Self>,
    ) -> Create<Vec<Self>, structure_training_objectives::table> {
        insert_into(structure_training_objectives::table).values(training_objective_ids)
    }
}

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StructureObjectiveRest {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub training_objective_id: Uuid,
}

impl From<StructureObjective> for StructureObjectiveRest {
    fn from(structure_objective: StructureObjective) -> Self {
        Self {
            id: structure_objective.id,
            training_objective_id: structure_objective.training_objective_id,
        }
    }
}

#[derive(
    Insertable,
    Identifiable,
    Associations,
    Queryable,
    Selectable,
    Debug,
    PartialEq,
    Eq,
    Clone,
    Serialize,
    Deserialize,
)]
#[serde(rename_all = "camelCase")]
#[diesel(belongs_to(Structure, foreign_key = structure_id))]
#[diesel(table_name = structure_weaknesses)]
pub struct Weakness {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub structure_id: Uuid,
    pub weakness: String,
}

impl Weakness {
    pub fn new(structure_id: Uuid, weakness: WeaknessRest) -> Self {
        Self {
            id: weakness.id,
            structure_id,
            weakness: weakness.weakness,
        }
    }

    pub fn by_structure(
        structure: &Structure,
    ) -> SelectByIdFromAllReference<
        structure_weaknesses::table,
        structure_weaknesses::structure_id,
        Self,
    > {
        Self::belonging_to(structure).select(Self::as_select())
    }

    pub fn batch_insert(weaknesses: Vec<Self>) -> Create<Vec<Self>, structure_weaknesses::table> {
        insert_into(structure_weaknesses::table).values(weaknesses)
    }
}

#[derive(
    Insertable, Identifiable, Queryable, Selectable, Debug, PartialEq, Associations, Eq, Clone, Hash,
)]
#[diesel(belongs_to(Order, foreign_key = order_id))]
#[diesel(table_name = environments)]
pub struct Environment {
    pub id: Uuid,
    pub order_id: Uuid,
    pub name: String,
    pub category: String,
    pub size: i32,
    pub additional_information: Option<String>,
}

impl Environment {
    pub fn new(order_id: Uuid, environment_rest: EnvironmentRest) -> Self {
        Self {
            order_id,
            id: environment_rest.id,
            name: environment_rest.name,
            category: environment_rest.category,
            size: environment_rest.size,
            additional_information: environment_rest.additional_information,
        }
    }

    pub fn create_insert(&self) -> Create<&Self, environments::table> {
        insert_into(environments::table).values(self)
    }

    pub fn hard_delete_by_id(id: Uuid) -> DeleteById<environments::id, environments::table> {
        diesel::delete(environments::table.filter(environments::id.eq(id)))
    }

    pub fn hard_delete(&self) -> DeleteById<environments::id, environments::table> {
        Self::hard_delete_by_id(self.id)
    }

    fn all() -> All<environments::table, Self> {
        environments::table.select(Self::as_select())
    }

    pub fn by_id(id: Uuid) -> SelectByIdFromAll<environments::table, environments::id, Self> {
        Self::all().filter(environments::id.eq(id))
    }

    pub fn by_order(
        order: &Order,
    ) -> SelectByIdFromAllReference<environments::table, environments::order_id, Self> {
        Self::belonging_to(order).select(Self::as_select())
    }
}

#[derive(
    Insertable, Identifiable, Queryable, Selectable, Debug, PartialEq, Associations, Eq, Clone, Hash,
)]
#[diesel(belongs_to(Environment, foreign_key = environment_id))]
#[diesel(table_name = environment_weakness)]
pub struct EnvironmentWeakness {
    pub id: Uuid,
    pub environment_id: Uuid,
    pub weakness: String,
}

impl EnvironmentWeakness {
    pub fn new(environment_id: Uuid, weakness: WeaknessRest) -> Self {
        Self {
            id: weakness.id,
            environment_id,
            weakness: weakness.weakness,
        }
    }

    pub fn by_environment(
        environment: &Environment,
    ) -> SelectByIdFromAllReference<
        environment_weakness::table,
        environment_weakness::environment_id,
        Self,
    > {
        Self::belonging_to(environment).select(Self::as_select())
    }

    pub fn batch_insert(weaknesses: Vec<Self>) -> Create<Vec<Self>, environment_weakness::table> {
        insert_into(environment_weakness::table).values(weaknesses)
    }
}

#[derive(
    Insertable, Identifiable, Queryable, Selectable, Debug, PartialEq, Associations, Eq, Clone, Hash,
)]
#[diesel(belongs_to(Environment, foreign_key = environment_id))]
#[diesel(table_name = environment_strength)]
pub struct EnvironmentStrength {
    pub id: Uuid,
    pub environment_id: Uuid,
    pub strength: String,
}

impl EnvironmentStrength {
    pub fn new(environment_id: Uuid, strength: StrengthRest) -> Self {
        Self {
            id: strength.id,
            environment_id,
            strength: strength.strength,
        }
    }

    pub fn by_environment(
        environment: &Environment,
    ) -> SelectByIdFromAllReference<
        environment_strength::table,
        environment_strength::environment_id,
        Self,
    > {
        Self::belonging_to(environment).select(Self::as_select())
    }

    pub fn batch_insert(strengths: Vec<Self>) -> Create<Vec<Self>, environment_strength::table> {
        insert_into(environment_strength::table).values(strengths)
    }
}

#[derive(
    Insertable, Identifiable, Queryable, Selectable, Debug, PartialEq, Associations, Eq, Clone, Hash,
)]
#[diesel(belongs_to(Order, foreign_key = order_id))]
#[diesel(table_name = custom_elements)]
pub struct CustomElement {
    pub id: Uuid,
    pub order_id: Uuid,
    pub name: String,
    pub description: String,
    pub environment_id: Uuid,
}

impl CustomElement {
    pub fn new(order_id: Uuid, custom_element_rest: CustomElementRest) -> Self {
        Self {
            order_id,
            id: custom_element_rest.id,
            name: custom_element_rest.name,
            description: custom_element_rest.description,
            environment_id: custom_element_rest.environment_id,
        }
    }

    pub fn create_insert(&self) -> Create<&Self, custom_elements::table> {
        insert_into(custom_elements::table).values(self)
    }

    pub fn hard_delete_by_id(id: Uuid) -> DeleteById<custom_elements::id, custom_elements::table> {
        diesel::delete(custom_elements::table.filter(custom_elements::id.eq(id)))
    }

    pub fn hard_delete(&self) -> DeleteById<custom_elements::id, custom_elements::table> {
        Self::hard_delete_by_id(self.id)
    }

    fn all() -> All<custom_elements::table, Self> {
        custom_elements::table.select(Self::as_select())
    }

    pub fn by_id(id: Uuid) -> SelectByIdFromAll<custom_elements::table, custom_elements::id, Self> {
        Self::all().filter(custom_elements::id.eq(id))
    }

    pub fn by_order(
        order: &Order,
    ) -> SelectByIdFromAllReference<custom_elements::table, custom_elements::order_id, Self> {
        Self::belonging_to(order).select(Self::as_select())
    }
}

#[derive(
    Insertable, Identifiable, Queryable, Selectable, Debug, PartialEq, Associations, Eq, Clone, Hash,
)]
#[diesel(belongs_to(Order, foreign_key = order_id))]
#[diesel(table_name = plots)]
pub struct Plot {
    pub id: Uuid,
    pub order_id: Uuid,
    pub name: String,
    pub description: String,
    pub start_time: NaiveDateTime,
    pub end_time: NaiveDateTime,
}

impl Plot {
    pub fn new(order_id: Uuid, plot_rest: PlotRest) -> Self {
        Self {
            order_id,
            id: plot_rest.id,
            name: plot_rest.name,
            description: plot_rest.description,
            start_time: plot_rest.start_time,
            end_time: plot_rest.end_time,
        }
    }

    pub fn create_insert(&self) -> Create<&Self, plots::table> {
        insert_into(plots::table).values(self)
    }

    pub fn hard_delete_by_id(id: Uuid) -> DeleteById<plots::id, plots::table> {
        diesel::delete(plots::table.filter(plots::id.eq(id)))
    }

    pub fn hard_delete(&self) -> DeleteById<plots::id, plots::table> {
        Self::hard_delete_by_id(self.id)
    }

    fn all() -> All<plots::table, Self> {
        plots::table.select(Self::as_select())
    }

    pub fn by_id(id: Uuid) -> SelectByIdFromAll<plots::table, plots::id, Self> {
        Self::all().filter(plots::id.eq(id))
    }

    pub fn by_order(
        order: &Order,
    ) -> SelectByIdFromAllReference<plots::table, plots::order_id, Self> {
        Self::belonging_to(order).select(Self::as_select())
    }
}

#[derive(
    Insertable, Identifiable, Queryable, Selectable, Debug, PartialEq, Associations, Eq, Clone, Hash,
)]
#[diesel(belongs_to(Plot, foreign_key = plot_id))]
#[diesel(table_name = plot_points)]
pub struct PlotPoint {
    pub id: Uuid,
    pub plot_id: Uuid,
    pub objective_id: Uuid,
    pub name: String,
    pub description: String,
    pub trigger_time: NaiveDateTime,
}

impl PlotPoint {
    pub fn new(plot_id: Uuid, plot_point: PlotPointRest) -> Self {
        Self {
            plot_id,
            id: plot_point.id,
            objective_id: plot_point.objective_id,
            description: plot_point.description,
            name: plot_point.name,
            trigger_time: plot_point.trigger_time,
        }
    }

    pub fn by_plot(
        plot: &Plot,
    ) -> SelectByIdFromAllReference<plot_points::table, plot_points::plot_id, Self> {
        Self::belonging_to(plot).select(Self::as_select())
    }

    pub fn batch_insert(weaknesses: Vec<Self>) -> Create<Vec<Self>, plot_points::table> {
        insert_into(plot_points::table).values(weaknesses)
    }
}

#[derive(
    Insertable, Identifiable, Queryable, Selectable, Debug, PartialEq, Associations, Eq, Clone, Hash,
)]
#[diesel(belongs_to(PlotPoint, foreign_key = plot_point_id))]
#[diesel(table_name = plot_point_structures)]
pub struct PlotPointStructure {
    pub id: Uuid,
    pub plot_point_id: Uuid,
    pub structure_id: Uuid,
}

impl PlotPointStructure {
    pub fn new(plot_point_id: Uuid, plot_point_structure: PlotPointStructureRest) -> Self {
        Self {
            id: plot_point_structure.id,
            plot_point_id,
            structure_id: plot_point_structure.structure_id,
        }
    }

    pub fn by_plot_point(
        plot_point: &PlotPoint,
    ) -> SelectByIdFromAllReference<
        plot_point_structures::table,
        plot_point_structures::plot_point_id,
        Self,
    > {
        Self::belonging_to(plot_point).select(Self::as_select())
    }

    pub fn batch_insert(weaknesses: Vec<Self>) -> Create<Vec<Self>, plot_point_structures::table> {
        insert_into(plot_point_structures::table).values(weaknesses)
    }
}

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WeaknessRest {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub weakness: String,
}

impl From<Weakness> for WeaknessRest {
    fn from(weakness: Weakness) -> Self {
        Self {
            id: weakness.id,
            weakness: weakness.weakness,
        }
    }
}

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StrengthRest {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub strength: String,
}

impl From<EnvironmentStrength> for StrengthRest {
    fn from(strength: EnvironmentStrength) -> Self {
        Self {
            id: strength.id,
            strength: strength.strength,
        }
    }
}

impl From<EnvironmentWeakness> for WeaknessRest {
    fn from(environment_weakness: EnvironmentWeakness) -> Self {
        Self {
            id: environment_weakness.id,
            weakness: environment_weakness.weakness,
        }
    }
}

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CustomElementRest {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub environment_id: Uuid,
    pub name: String,
    pub description: String,
}

impl From<CustomElement> for CustomElementRest {
    fn from(custom_element: CustomElement) -> Self {
        Self {
            id: custom_element.id,
            environment_id: custom_element.environment_id,
            name: custom_element.name,
            description: custom_element.description,
        }
    }
}

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PlotRest {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub name: String,
    pub description: String,
    pub start_time: NaiveDateTime,
    pub end_time: NaiveDateTime,
    pub plot_points: Option<Vec<PlotPointRest>>,
}

impl From<(Plot, Vec<PlotPointRest>)> for PlotRest {
    fn from((plot, plot_points): (Plot, Vec<PlotPointRest>)) -> Self {
        Self {
            id: plot.id,
            name: plot.name,
            description: plot.description,
            start_time: plot.start_time,
            end_time: plot.end_time,
            plot_points: Some(plot_points),
        }
    }
}

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PlotPointRest {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub objective_id: Uuid,
    pub name: String,
    pub description: String,
    pub trigger_time: NaiveDateTime,
    pub structure_ids: Option<Vec<PlotPointStructureRest>>,
}

impl From<(PlotPoint, Vec<PlotPointStructureRest>)> for PlotPointRest {
    fn from((plot_point, structures): (PlotPoint, Vec<PlotPointStructureRest>)) -> Self {
        Self {
            id: plot_point.id,
            objective_id: plot_point.objective_id,
            name: plot_point.name,
            description: plot_point.description,
            trigger_time: plot_point.trigger_time,
            structure_ids: Some(structures),
        }
    }
}

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PlotPointStructureRest {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub structure_id: Uuid,
}

impl From<PlotPointStructure> for PlotPointStructureRest {
    fn from(plot_point_structure: PlotPointStructure) -> Self {
        Self {
            id: plot_point_structure.id,
            structure_id: plot_point_structure.structure_id,
        }
    }
}

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StructureRest {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub name: String,
    pub description: Option<String>,
    pub parent_id: Option<Uuid>,
    pub weaknesses: Option<Vec<WeaknessRest>>,
    pub skills: Option<Vec<SkillRest>>,
    pub training_objective_ids: Option<Vec<StructureObjectiveRest>>,
}

impl
    From<(
        Structure,
        (
            Vec<SkillRest>,
            Vec<StructureObjectiveRest>,
            Vec<WeaknessRest>,
        ),
    )> for StructureRest
{
    fn from(
        (structure, (skills, structure_objectives, weaknesses)): (
            Structure,
            (
                Vec<SkillRest>,
                Vec<StructureObjectiveRest>,
                Vec<WeaknessRest>,
            ),
        ),
    ) -> Self {
        Self {
            id: structure.id,
            name: structure.name,
            description: structure.description,
            parent_id: structure.parent_id,
            weaknesses: Some(weaknesses),
            skills: Some(skills),
            training_objective_ids: Some(structure_objectives),
        }
    }
}

pub type PlotWithElements = HashMap<Plot, HashMap<PlotPoint, Vec<PlotPointStructure>>>;

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ThreatRest {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub threat: String,
}

impl From<Threat> for ThreatRest {
    fn from(threat: Threat) -> Self {
        Self {
            id: threat.id,
            threat: threat.threat,
        }
    }
}

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TrainingObjectiveRest {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub objective: String,
    pub threats: Vec<ThreatRest>,
}

impl From<(TrainingObjective, Vec<ThreatRest>)> for TrainingObjectiveRest {
    fn from((objective, threats): (TrainingObjective, Vec<ThreatRest>)) -> Self {
        Self {
            id: objective.id,
            objective: objective.objective,
            threats,
        }
    }
}

pub type StructureWithElements = HashMap<
    Structure,
    (
        Vec<SkillRest>,
        Vec<StructureObjectiveRest>,
        Vec<WeaknessRest>,
    ),
>;

#[derive(Debug, PartialEq, Eq, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EnvironmentRest {
    #[serde(default = "Uuid::random")]
    pub id: Uuid,
    pub name: String,
    pub category: String,
    pub size: i32,
    pub additional_information: Option<String>,
    pub weaknesses: Option<Vec<WeaknessRest>>,
    pub strengths: Option<Vec<StrengthRest>>,
}

pub type EnvironmentElements = HashMap<Environment, (Vec<WeaknessRest>, Vec<StrengthRest>)>;

impl From<(Environment, (Vec<WeaknessRest>, Vec<StrengthRest>))> for EnvironmentRest {
    fn from(
        (environment, (weaknesses, strengths)): (
            Environment,
            (Vec<WeaknessRest>, Vec<StrengthRest>),
        ),
    ) -> Self {
        Self {
            id: environment.id,
            name: environment.name,
            category: environment.category,
            size: environment.size,
            additional_information: environment.additional_information,
            weaknesses: Some(weaknesses),
            strengths: Some(strengths),
        }
    }
}

#[derive(Debug, PartialEq, Eq, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OrderRest {
    pub id: Uuid,
    pub name: String,
    pub client_id: String,
    pub status: OrderStatus,
    pub training_objectives: Vec<TrainingObjectiveRest>,
    pub structures: Vec<StructureRest>,
    pub environments: Vec<EnvironmentRest>,
    pub custom_elements: Vec<CustomElementRest>,
    pub plots: Vec<PlotRest>,
    pub created_at: NaiveDateTime,
    pub updated_at: NaiveDateTime,
}

impl
    From<(
        Order,
        HashMap<TrainingObjective, Vec<ThreatRest>>,
        StructureWithElements,
        EnvironmentElements,
        Vec<CustomElement>,
        PlotWithElements,
    )> for OrderRest
{
    fn from(
        (order, training_objectives, structures, environments, custom_elements, plots): (
            Order,
            HashMap<TrainingObjective, Vec<ThreatRest>>,
            StructureWithElements,
            EnvironmentElements,
            Vec<CustomElement>,
            PlotWithElements,
        ),
    ) -> Self {
        let structures = structures
            .into_iter()
            .map(|(structure, elements)| (structure, elements).into())
            .collect();
        let environments = environments
            .into_iter()
            .map(|(environment, elements)| (environment, elements).into())
            .collect();
        let training_objectives: Vec<TrainingObjectiveRest> = training_objectives
            .into_iter()
            .map(|threats_by_objective| threats_by_objective.into())
            .collect();
        let custom_elements: Vec<CustomElementRest> = custom_elements
            .into_iter()
            .map(|custom_element| custom_element.into())
            .collect();
        let plots: Vec<PlotRest> = plots
            .into_iter()
            .map(|plot_map| {
                let (plot, plot_point_map) = plot_map;
                let plot_points: Vec<PlotPointRest> = plot_point_map
                    .into_iter()
                    .map(|(plot_point, plot_point_structures)| {
                        let plot_point_structures: Vec<PlotPointStructureRest> =
                            plot_point_structures
                                .into_iter()
                                .map(|plot_point_structure| plot_point_structure.into())
                                .collect();
                        PlotPointRest::from((plot_point, plot_point_structures))
                    })
                    .collect();
                PlotRest::from((plot, plot_points))
            })
            .collect();
        Self {
            id: order.id,
            name: order.name,
            client_id: order.client_id,
            status: order.status,
            training_objectives,
            structures,
            environments,
            custom_elements,
            plots,
            created_at: order.created_at,
            updated_at: order.updated_at,
        }
    }
}
