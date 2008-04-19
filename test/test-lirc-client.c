/* This test code is based on irexec.c in lirc.
 * Build with 
 * gcc test_lirc_client.c -llirc_client
 * 
 * This depends on 
 * - A correct /etc/lirc/lircd.conf, which maps the key names to the key codes supplied by your IR remote.
 * - A running lircd, with the corred device specified. For instance: “/usr/sbin/lircd –device=/dev/lirc0″.
 * - An example.lircrc file, which maps the key names to "command" names that an application would understand.
 * On Ubuntu/Debian, dpkg-reconfigure lirc can do this for common remotes.
 *
 * Murray Cumming, Openismus GmbH 
 */

#include <lirc/lirc_client.h>

#include <errno.h>
#include <unistd.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char *progname;

int main(int argc, char *argv[])
{
	struct lirc_config *config;
        const char *lirc_config = NULL;

	progname=argv[0];
	if(argc>2)
	{
		fprintf(stderr,"Usage: %s <config file>\n",progname);
		exit(EXIT_FAILURE);
	}

	if(lirc_init("openismus-lirc-test",1)==-1)
          exit(EXIT_FAILURE);

        printf("lirc_init(): succeeded.\n");

	lirc_config = (argc==2 ? argv[1]:"./example.lircrc");
	if(lirc_readconfig((char*)lirc_config, &config,NULL)==0)
	{
                printf("lirc_readconfig(): succeeded.\n");

		char *code;
		char *c;
		int ret;

		while(lirc_nextcode(&code)==0)
		{
                        printf("lirc_nextcode(): succeeded.\n");
			if(code==NULL) continue;
			while((ret=lirc_code2char(config,code,&c))==0 &&
			      c!=NULL)
			{
                                printf("lirc_code2char(): succeeded.\n");
				printf("Command received: \"%s\"\n", c);
				
			}
			free(code);
			if(ret==-1) break;
		}
		lirc_freeconfig(config);
	}

	lirc_deinit();
	exit(EXIT_SUCCESS);
}


