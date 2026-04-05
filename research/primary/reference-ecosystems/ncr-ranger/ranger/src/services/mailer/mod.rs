use lettre::{
    transport::smtp::{authentication::Credentials, response::Response, Error},
    Message, SmtpTransport, Transport,
};

use crate::configuration::MailerConfiguration;

#[derive(Debug, Clone)]
pub struct Mailer {
    pub configuration: MailerConfiguration,
}

impl Mailer {
    pub fn new(configuration: MailerConfiguration) -> Self {
        Self { configuration }
    }

    pub fn send_message(&self, message: Message) -> Result<Response, Error> {
        let credentials = Credentials::new(
            self.configuration.username.clone(),
            self.configuration.password.clone(),
        );

        let client = SmtpTransport::starttls_relay(&self.configuration.server_address)?
            .credentials(credentials)
            .build();

        client.send(&message)
    }
}
