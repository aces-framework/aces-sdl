use actix::{Actor, Context, Handler, Message};
use anyhow::Result;
use indicatif::{ProgressBar, ProgressStyle};
use std::time::Duration;

#[derive(Debug)]
pub enum ProgressStatus {
    InProgress(String),
    Done,
}

pub struct SpinnerProgressBar(ProgressBar, String, bool);

impl SpinnerProgressBar {
    pub fn new(final_message: String) -> Result<Self> {
        let bar = ProgressBar::new(100);
        let style = ProgressStyle::default_spinner()
            .template("[{elapsed_precise}] {spinner:.cyan} {msg}")?
            .tick_chars("⠁⠂⠄⡀⢀⠠⠐⠈ ")
            .progress_chars("█▉▊▋▌▍▎▏  ");
        bar.set_style(style);
        Ok(Self(bar, final_message, false))
    }

    fn show(&mut self) {
        if !self.2 {
            self.2 = true;
            self.0.enable_steady_tick(Duration::from_millis(75));
            self.0.set_message("Starting....");
            self.0.tick();
        }
    }

    fn finish(&mut self) -> Result<()> {
        if self.2 {
            self.0.set_style(
                ProgressStyle::default_spinner()
                    .template("[{elapsed_precise}] {msg:.green.bold}")?,
            );
            self.0.finish_with_message(self.1.clone());
            self.2 = false;
        }
        Ok(())
    }
}

#[derive(Message)]
#[rtype(result = "Result<()>")]
pub struct AdvanceProgressBar(pub ProgressStatus);

impl Actor for SpinnerProgressBar {
    type Context = Context<Self>;
}

impl Handler<AdvanceProgressBar> for SpinnerProgressBar {
    type Result = Result<()>;

    fn handle(&mut self, msg: AdvanceProgressBar, _ctx: &mut Context<Self>) -> Self::Result {
        match msg.0 {
            ProgressStatus::InProgress(progress_string) => {
                self.show();
                self.0.set_message(progress_string);

                self.0.tick();
            }
            ProgressStatus::Done => {
                self.finish()?;
            }
        }
        Ok(())
    }
}
