use actix_web::{web::scope, web::Data, App, HttpServer};
use anyhow::Error;
use ranger::app_setup;
use ranger::middleware::authentication::AuthenticationMiddlewareFactory;
use ranger::middleware::deployment::DeploymentMiddlewareFactory;
use ranger::middleware::exercise::ExerciseMiddlewareFactory;
use ranger::middleware::keycloak::KeycloakAccessMiddlewareFactory;
use ranger::middleware::metric::MetricMiddlewareFactory;
use ranger::middleware::order::OrderMiddlewareFactory;
use ranger::middleware::participant_authentication::ParticipantAccessMiddlewareFactory;
use ranger::roles::RangerRole;
use ranger::routes::admin::email::{
    add_email_template, delete_email, delete_email_template, get_email, get_email_form,
    get_email_template, get_email_templates, get_emails, send_email,
};
use ranger::routes::admin::event::{get_admin_event_info_data, get_exercise_deployment_events};
use ranger::routes::admin::groups::get_participant_groups_users;
use ranger::routes::admin::metric::{
    delete_metric, download_metric_artifact, get_admin_metric, get_admin_metrics,
    update_admin_metric,
};
use ranger::routes::admin::order::{get_order_admin, get_orders_admin};
use ranger::routes::admin::scenario::get_admin_exercise_deployment_scenario;
use ranger::routes::deployers::{default_deployer, get_deployers};
use ranger::routes::deputy_query::{
    check_package_exists, get_deputy_banner_file, get_deputy_packages_by_type,
    get_exercise_by_source,
};
use ranger::routes::client::order::{create_custom_element, create_environment, create_plot, create_structure, create_training_objective, delete_custom_element, delete_custom_element_file, delete_environment, delete_plot, delete_structure, delete_training_objective, get_custom_element_file, get_orders_client, update_custom_element, update_environment, update_plot, update_structure, update_training_objective, upload_custom_element_file};
use ranger::routes::exercise::{
    add_banner, add_exercise, add_exercise_deployment, add_participant, delete_banner,
    delete_exercise, delete_exercise_deployment, delete_participant, get_admin_participants,
    get_banner, get_exercise, get_exercise_deployment, get_exercise_deployment_elements,
    get_exercise_deployment_scores, get_exercise_deployment_users, get_exercise_deployments,
    get_exercises, subscribe_to_exercise, update_banner, update_exercise,
};
use ranger::routes::logger::subscribe_to_logs_with_level;
use ranger::routes::order::{create_order, get_order, update_order};
use ranger::routes::participant::deployment::{
    get_participant_deployment, get_participant_deployments,
    get_participant_node_deployment_elements, subscribe_participant_to_deployment,
};
use ranger::routes::participant::event_info::get_participant_event_info_data;
use ranger::routes::participant::events::get_participant_events;
use ranger::routes::participant::metric::{
    add_metric, get_participant_metric, get_participant_metrics, update_participant_metric,
};
use ranger::routes::participant::participants::get_own_participants;
use ranger::routes::participant::scenario::get_participant_exercise_deployment_scenario;
use ranger::routes::participant::score::get_participant_exercise_deployment_scores;
use ranger::routes::participant::{get_participant_exercise, get_participant_exercises};

use ranger::routes::{
    admin::groups::get_participant_groups,
    basic::{status, version},
    upload::upload_participant_artifact,
};

#[actix_web::main]
async fn main() -> Result<(), Error> {
    let (host, port, app_state) = app_setup(std::env::args().collect()).await?;
    let app_data = Data::new(app_state);

    HttpServer::new(move || {
        let admin_auth_middleware = AuthenticationMiddlewareFactory(RangerRole::Admin);
        let participant_auth_middleware = AuthenticationMiddlewareFactory(RangerRole::Participant);
        let client_auth_middleware = AuthenticationMiddlewareFactory(RangerRole::Client);
        App::new()
            .app_data(app_data.to_owned())
            .service(status)
            .service(version)
            .service(
                scope("/api/v1")
                    .wrap(KeycloakAccessMiddlewareFactory)
                    .service(
                        scope("/admin")
                        .service(
                            scope("/order")
                            .service(get_orders_admin)
                            .service(
                                scope("/{order_uuid}")
                                    .wrap(OrderMiddlewareFactory)
                                    .service(get_order_admin)
                                    .service(update_order)
                                )
                        )
                        .service(
                            scope("/query")
                                .service(
                                    scope("/package")
                                        .service(get_deputy_packages_by_type)
                                        .service(
                                            scope("/exercise")
                                                .service(get_exercise_by_source)
                                                .service(
                                                    scope("/banner")
                                                        .service(get_deputy_banner_file)
                                                )
                                        )
                                        .service(
                                            scope("/check")
                                                .service(check_package_exists)
                                        )
                                )
                            )
                            .service(
                                scope("/exercise")
                                    .service(get_exercises)
                                    .service(add_exercise)
                                    .service(
                                        scope("/{exercise_uuid}")
                                            .wrap(ExerciseMiddlewareFactory)
                                            .service(get_exercise)
                                            .service(update_exercise)
                                            .service(delete_exercise)
                                            .service(subscribe_to_exercise)
                                            .service(
                                                scope("/deployment")
                                                    .service(get_exercise_deployments)
                                                    .service(add_exercise_deployment)
                                                    .service(
                                                        scope("/{deployment_uuid}")
                                                            .wrap(DeploymentMiddlewareFactory)
                                                            .service(get_exercise_deployment)
                                                            .service(
                                                                get_exercise_deployment_elements,
                                                            )
                                                            .service(delete_exercise_deployment)
                                                            .service(get_admin_participants)
                                                            .service(add_participant)
                                                            .service(delete_participant)
                                                            .service(get_exercise_deployment_scores)
                                                            .service(
                                                                get_admin_exercise_deployment_scenario,
                                                            )
                                                            .service(get_exercise_deployment_users)
                                                            .service(
                                                                scope("/event")
                                                                    .service(get_exercise_deployment_events)
                                                                    .service(
                                                                        scope("/{event_info_id}")
                                                                            .service(get_admin_event_info_data)
                                                                    )
                                                            )
                                                            .service(
                                                                scope("/metric") 
                                                                .service(get_admin_metrics)
                                                                .service(
                                                                    scope("/{metric_uuid}")
                                                                    .wrap(MetricMiddlewareFactory)
                                                                        .service(get_admin_metric)
                                                                        .service(update_admin_metric)
                                                                        .service(delete_metric)
                                                                        .service(download_metric_artifact)
                                                                    ),
                                                            ),
                                                    ),
                                            )
                                            .service(
                                                scope("/banner")
                                                .service(add_banner)
                                                .service(get_banner)
                                                .service(update_banner)
                                                .service(delete_banner)
                                            )
                                            .service(
                                                scope("/email")
                                                .service(get_emails)
                                                .service(get_email)
                                                .service(send_email)
                                                .service(delete_email)
                                            )
                                            .service(
                                                scope("/email-form")
                                                .service(get_email_form)
                                            )
                                    ),
                            )
                            .service(
                                scope("/deployer")
                                    .service(get_deployers)
                                    .service(default_deployer),
                            )
                            .service(
                                scope("/group")
                                    .service(get_participant_groups)
                                    .service(get_participant_groups_users),
                            )
                            .service(
                                scope("/log")
                                    .service(subscribe_to_logs_with_level)
                            )
                            .service(
                                scope("/email_template")
                                    .service(add_email_template)
                                    .service(get_email_templates)
                                    .service(get_email_template)
                                    .service(delete_email_template)
                            )
                            .wrap(admin_auth_middleware),
                    )
                    .service(
                    scope("/client")
                        .service(
                            scope("/order")
                            .service(create_order)
                            .service(get_orders_client)
                            .service(
                                scope("/{order_uuid}")
                                    .wrap(OrderMiddlewareFactory)
                                    .service(get_order)
                                    .service(update_order)
                                    .service(create_training_objective)
                                    .service(delete_training_objective)
                                    .service(update_training_objective)
                                    .service(create_structure)
                                    .service(delete_structure)
                                    .service(update_structure)
                                    .service(create_environment)
                                    .service(update_environment)
                                    .service(delete_environment)
                                    .service(create_custom_element)
                                    .service(update_custom_element)
                                    .service(upload_custom_element_file)
                                    .service(delete_custom_element)
                                    .service(delete_custom_element_file)
                                    .service(get_custom_element_file)
                                    .service(create_plot)
                                    .service(update_plot)
                                    .service(delete_plot)
                                )
                        )
                      .wrap(client_auth_middleware)
                        
                    )
                    .service(
                        scope("/participant")
                            .service(
                                scope("/exercise")
                                    .service(get_participant_exercises)
                                    .service(
                                        scope("/{exercise_uuid}")
                                            .service(get_participant_exercise)
                                            .service(
                                                scope("/deployment")
                                                    .service(get_participant_deployments)
                                                    .service(
                                                        scope("/{deployment_uuid}")
                                                            .service(get_participant_deployment)
                                                            .service(
                                                                get_participant_exercise_deployment_scenario,
                                                            )
                                                            .service(get_exercise_deployment_users)
                                                            .service(get_own_participants)
                                                            .wrap(DeploymentMiddlewareFactory)
                                                            .service(
                                                                scope("/entity")
                                                                .service(
                                                                    scope("/{entity_selector}")
                                                                            .wrap(ParticipantAccessMiddlewareFactory)
                                                                            .service(
                                                                                scope("/score")
                                                                                .service(get_participant_exercise_deployment_scores)
                                                                            )
                                                                            .service(
                                                                                scope("/event")
                                                                                .service(get_participant_events)
                                                                                .service(
                                                                                    scope("/{event_info_id}")
                                                                                        .service(get_participant_event_info_data)
                                                                            )
                                                                            )
                                                                            .service(
                                                                                scope("/deployment_element")
                                                                                .service(get_participant_node_deployment_elements)
                                                                            )
                                                                            .wrap(DeploymentMiddlewareFactory)
                                                                            .service(
                                                                                scope("/metric")
                                                                                .service(get_participant_metrics)
                                                                                .service(add_metric)
                                                                                .service(
                                                                                    scope("/{metric_uuid}")
                                                                                    .wrap(MetricMiddlewareFactory)
                                                                                        .service(get_participant_metric)
                                                                                        .service(update_participant_metric)
                                                                                        .service(upload_participant_artifact)
                                                                                    ),
                                                                            )
                                                                            .service(
                                                                                scope("/websocket")
                                                                                .service(subscribe_participant_to_deployment)
                                                                            )
                                                                )
                                                            )
                                                    ),
                                            )
                                            .service(scope("/banner")
                                                    .service(get_banner)
                                            )
                                            .wrap(ExerciseMiddlewareFactory),
                                    ),
                            )
                            .wrap(participant_auth_middleware),
                    ),
            )
    })
    .bind((host, port))?
    .run()
    .await?;
    Ok(())
}
