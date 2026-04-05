use crate::constants::{LOCKFILE_SLEEP_DURATION, LOCKFILE_TRIES};
use anyhow::{anyhow, Result};
use lockfile::Lockfile;
use std::{path::Path, thread::sleep};

pub trait Standoff: Sized {
    type Lockfile;
    fn new(lockfile_path: &Path) -> Result<Self>;
}
impl Standoff for Lockfile {
    type Lockfile = Self;
    fn new(lockfile_path: &Path) -> Result<Self> {
        let mut tries = *LOCKFILE_TRIES;
        let mut lockfile = Self::create(lockfile_path);

        while matches!(lockfile.as_ref().err(), Some(lockfile::Error::LockTaken)) && tries > 0 {
            tries -= 1;
            lockfile = Self::create(lockfile_path);
            sleep(*LOCKFILE_SLEEP_DURATION);
        }
        if lockfile.as_ref().is_err() && tries == 0 {
            return Err(anyhow!("Timeout creating lockfile"));
        }
        lockfile.map_err(|err| anyhow!("Error creating lockfile: {:?}", err))
    }
}

#[cfg(test)]
mod tests {
    use std::{
        path::PathBuf,
        thread::{self, sleep, JoinHandle},
        time::Duration,
    };

    use crate::{constants::LOCKFILE, lockfile::Standoff};
    use anyhow::Result;
    use futures::future::join_all;
    use lockfile::Lockfile;
    use rand::Rng;

    #[test]
    fn lockfile_is_created() -> Result<()> {
        let temp_dir = tempfile::tempdir()?;
        let lockfile_path = temp_dir.path().join(LOCKFILE);
        let lockfile = Lockfile::new(&lockfile_path);
        assert!(lockfile.is_ok());
        assert!(lockfile_path.is_file());
        Ok(())
    }

    #[test]
    fn lockfile_is_released() -> Result<()> {
        let temp_dir = tempfile::tempdir()?;
        let lockfile_path = temp_dir.path().join(LOCKFILE);
        let lockfile = Lockfile::new(&lockfile_path)?;
        lockfile.release()?;
        assert!(!lockfile_path.is_file());
        Ok(())
    }

    async fn spawn_some_heavy_lockfile_computation(
        lockfile_path: PathBuf,
    ) -> JoinHandle<Result<(), anyhow::Error>> {
        thread::spawn(move || {
            let lockfile = Lockfile::new(&lockfile_path)?;
            sleep(Duration::from_millis(rand::thread_rng().gen_range(10..200)));
            lockfile.release()?;
            Ok::<_, anyhow::Error>(())
        })
    }

    #[actix_web::test]
    async fn concurrent_lockfile_requests_are_handled() -> Result<()> {
        let temp_dir = tempfile::tempdir()?;
        let lockfile_path = temp_dir.path().join(LOCKFILE);

        const CONCURRENT_REQUESTS: usize = 10;
        let requests = vec![0; CONCURRENT_REQUESTS];

        let join_handles =
            join_all(requests.iter().map(|_| async {
                spawn_some_heavy_lockfile_computation(lockfile_path.clone()).await
            }))
            .await;

        for handle in join_handles {
            assert!(handle.join().unwrap().is_ok());
        }
        Ok(())
    }
}
