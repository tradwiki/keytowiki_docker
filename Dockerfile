FROM python:3

WORKDIR /app

#Get packages
RUN apt-get update && apt-get install -yq lilypond sudo 

#Install audio packages
RUN DEBIAN_FRONTEND='noninteractive' apt-get update && DEBIAN_FRONTEND='noninteractive' apt-get install -yq jackd2
RUN apt-get update && apt-get install -yq libasound2-dev 
RUN apt-get update && apt-get install -yq libjack-jackd2-dev 
RUN apt-get update && apt-get install -yq patchage


#Install python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


#Get pywikibot source
RUN git clone https://gerrit.wikimedia.org/r/pywikibot/core.git

#Go into folder to get its requirements and update
WORKDIR core
RUN git submodule update --init
RUN pip install --no-cache-dir -r requirements.txt

#Get my my bot files from github
#set CACHEBUST2 to current time to force running the next instruction even though it was cached
ARG CACHEBUST2=1
RUN git clone https://github.com/yochie/keytowiki.git

#Copy its content into core folder
RUN cp -RT keytowiki/ ./

#overwrite main script with local version script for development ease (no need to push to github for testing)
COPY music_bot.py scripts/

#Create user and give it permissions
RUN export uid=1000 gid=1000 && \
    mkdir -p /home/developer && \
    echo "developer:x:${uid}:${gid}:Developer,,,:/home/developer:/bin/bash" >> /etc/passwd && \
    echo "developer:x:${uid}:" >> /etc/group && \
    echo "developer ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/developer && \
    chmod 0440 /etc/sudoers.d/developer && \
    chown ${uid}:${gid} -R /home/developer

#Enable audio group limits
RUN cp /etc/security/limits.d/audio.conf.disabled /etc/security/limits.d/audio.conf
RUN gpasswd -a developer audio

#take ownership of everything in core
RUN chown developer -R ./

#Set user
USER developer
ENV HOME /home/developer

#ENTRYPOINT [ "python", "pwb.py" , "music_bot" ]
ENTRYPOINT [ "bash" ]
